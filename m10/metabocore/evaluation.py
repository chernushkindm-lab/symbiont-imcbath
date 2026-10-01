"""Evidence-aware scoring and strictly chronological, run-isolated baselines."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from math import exp, log, sqrt, isfinite
from collections import defaultdict
from typing import Sequence, Mapping


def aware(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')
    return parsed


def assert_no_future_information(origin, evidence: Sequence[Mapping]):
    origin = aware(origin)
    for row in evidence:
        if aware(row['available_at']) > origin or aware(row['timestamp']) > origin:
            raise ValueError('future information in forecast: ' + str(row.get('evidence_id', 'unknown')))


@dataclass(frozen=True)
class ForecastPair:
    run_id: str
    segment_id: str
    interval_start: str
    interval_end: str
    forecast_origin: str
    observable: str
    predicted_observable: str
    observed: float
    predicted: float
    model: str
    evidence_id: str
    observation_class: str = 'measured'
    lower: float | None = None
    upper: float | None = None
    mean_volume_l: float | None = None
    used_as_constraint: bool = False
    independent_assay: bool = False
    excluded_reason: str | None = None

    def duration_h(self):
        result = (aware(self.interval_end) - aware(self.interval_start)).total_seconds() / 3600
        if result <= 0:
            raise ValueError('positive evaluation interval required')
        return result


def evaluate_pairs(pairs: Sequence[ForecastPair], *, relative_threshold: float = .01) -> dict:
    if not isfinite(relative_threshold) or relative_threshold <= 0:
        raise ValueError('positive relative-error threshold required')
    groups, excluded, rows, keys = defaultdict(list), [], [], set()
    for p in pairs:
        duration = p.duration_h()
        start, origin = aware(p.interval_start), aware(p.forecast_origin)
        key = (p.run_id, p.segment_id, p.interval_start, p.interval_end, p.forecast_origin, p.model, p.observable)
        if key in keys:
            raise ValueError('duplicate evaluation pair')
        keys.add(key)
        reason = p.excluded_reason
        if p.observable != p.predicted_observable:
            reason = 'observable_mismatch'
        elif p.observation_class not in {'measured', 'source-derived', 'recalculated'}:
            reason = 'not_observed_ground_truth'
        elif p.used_as_constraint:
            reason = 'target_used_as_model_constraint'
        elif origin > start:
            reason = 'forecast_origin_after_interval_start'
        elif not isfinite(p.observed) or not isfinite(p.predicted):
            reason = 'nonfinite_value'
        if (p.lower is None) != (p.upper is None):
            raise ValueError('prediction interval must have both endpoints')
        if p.lower is not None and (not isfinite(p.lower) or not isfinite(p.upper) or p.lower > p.upper):
            raise ValueError('invalid prediction interval')
        if reason:
            excluded.append({'evidence_id': p.evidence_id, 'reason': reason})
            continue
        gap = p.predicted - p.observed
        horizon = (aware(p.interval_end) - origin).total_seconds() / 3600
        row = asdict(p) | {'duration_h': duration, 'horizon_h': horizon,
                          'signed_gap': gap, 'absolute_error': abs(gap),
                          'relative_gap_percent': 100 * gap / p.observed if p.observed > relative_threshold else None}
        rows.append(row)
        groups[(p.run_id, p.segment_id, p.model, p.observable, horizon)].append(row)
    metrics = []
    for (run, segment, model, observable, horizon), values in groups.items():
        weight = sum(v['duration_h'] for v in values)
        interval_values = [v for v in values if v['lower'] is not None]
        interval_weight = sum(v['duration_h'] for v in interval_values)
        ordered = sorted(values, key=lambda v: aware(v['interval_start']))
        overlap = any(aware(a['interval_end']) > aware(b['interval_start']) for a, b in zip(ordered, ordered[1:]))
        mass_diff = None
        if observable == 'harvest_productivity_g_l_h' and not overlap and all(v['mean_volume_l'] is not None and isfinite(v['mean_volume_l']) and v['mean_volume_l'] > 0 for v in values):
            mass_diff = sum(v['signed_gap'] * v['duration_h'] * v['mean_volume_l'] for v in values)
        metrics.append({'run_id': run, 'segment_id': segment, 'model': model, 'observable': observable,
                        'horizon_h': horizon, 'count': len(values), 'evaluated_interval_h': weight,
                        'time_weighted_bias': sum(v['signed_gap'] * v['duration_h'] for v in values) / weight,
                        'time_weighted_mae': sum(v['absolute_error'] * v['duration_h'] for v in values) / weight,
                        'time_weighted_rmse': sqrt(sum(v['signed_gap']**2 * v['duration_h'] for v in values) / weight),
                        'prediction_interval_coverage': sum(v['duration_h'] * (v['lower'] <= v['observed'] <= v['upper']) for v in interval_values) / interval_weight if interval_weight else None,
                        'prediction_interval_mean_width': sum(v['duration_h'] * (v['upper'] - v['lower']) for v in interval_values) / interval_weight if interval_weight else None,
                        'integrated_harvest_mass_difference_g': mass_diff,
                        'overlapping_scored_intervals': overlap,
                        'independent_assay_count': sum(v['independent_assay'] for v in values)})
    return {'rows': rows, 'metrics': metrics, 'excluded': excluded, 'included_count': len(rows),
            'excluded_count': len(excluded), 'equation_version': 'paired-scoring-1.0',
            'qualification': 'scoring_does_not_establish_biological_validity',
            'uncertainty_warning': 'Shared calibration/input errors are correlated; no independent confidence interval inferred.'}


def capacity_gap(capacity: float, observed: float, *, observed_threshold: float = .01) -> dict:
    if not all(isfinite(v) for v in (capacity, observed)):
        raise ValueError('finite capacity and observation required')
    gap = capacity - observed
    return {'signed_capacity_gap': gap,
            'relative_to_observed_percent': 100 * gap / observed if observed > observed_threshold else None,
            'unused_capacity_fraction': gap / capacity if capacity > observed_threshold else None,
            'interpretation': 'conditional capacity comparison, not forecast error'}


def rolling_origin_splits(records: Sequence[Mapping], *, minimum_training: int = 5,
                          horizon_h: float = 4.) -> list[dict]:
    if minimum_training < 2 or horizon_h <= 0:
        raise ValueError('at least two training observations and a positive horizon required')
    grouped = defaultdict(list)
    for row in records:
        aware(row['timestamp']); aware(row['available_at'])
        grouped[(row['run_id'], row['segment_id'])].append(dict(row))
    splits = []
    for (run, segment), group in grouped.items():
        group.sort(key=lambda r: aware(r['timestamp']))
        for anchor in group:
            origin = aware(anchor['timestamp'])
            train = [r for r in group if aware(r['timestamp']) <= origin and aware(r['available_at']) <= origin]
            test = [r for r in group if origin < aware(r['timestamp']) <= origin + timedelta(hours=horizon_h)]
            if len(train) >= minimum_training and test:
                assert_no_future_information(origin, train)
                splits.append({'run_id': run, 'segment_id': segment, 'origin': origin.isoformat(),
                               'train': train, 'test': test})
    return splits


def rolling_origin_baselines(records: Sequence[Mapping], *, horizons_h=(1., 4., 12.),
                             minimum_training: int = 5, max_data_age_h: float = 2.,
                             training_window_h: float = 24., target_tolerance_h: float = .15) -> dict:
    """Persistence / training-only log-linear residue trend; no assay-delay invention.

    Records require timestamp, available_at, value, run_id, segment_id, evidence_id.
    The evaluation unit is the future point concentration, with its horizon used
    as a scoring weight. Baseline errors on OD-derived residue are not independent
    gravimetric validation. No intervals are fabricated from one trend fit.
    """
    if any(h <= 0 for h in horizons_h) or min(max_data_age_h, training_window_h) <= 0 or target_tolerance_h < 0:
        raise ValueError('invalid forecasting time policy')
    eligible, blocked = [], []
    for row in records:
        reason = None
        if row.get('available_at') is None:
            reason = 'availability_unknown'
        elif row.get('timestamp') is None:
            reason = 'event_time_unknown'
        elif row.get('value') is None or not isfinite(row['value']) or row['value'] <= 0:
            reason = 'missing_or_nonpositive_residue'
        elif row.get('classification', 'recalculated') not in {'measured', 'source-derived', 'recalculated'}:
            reason = 'not_observed_ground_truth'
        if reason:
            blocked.append({'evidence_id': row.get('evidence_id'), 'reason': reason})
        else:
            eligible.append(dict(row))
    result, seen = [], set()
    for split in rolling_origin_splits(eligible, minimum_training=minimum_training, horizon_h=max(horizons_h) + target_tolerance_h):
        origin = aware(split['origin'])
        train = [r for r in split['train'] if aware(r['timestamp']) >= origin - timedelta(hours=training_window_h)]
        if len(train) < minimum_training:
            continue
        last = train[-1]
        age = (origin - aware(last['timestamp'])).total_seconds() / 3600
        if age > max_data_age_h:
            blocked.append({'origin': split['origin'], 'reason': 'stale_input'})
            continue
        assert_no_future_information(origin, train)
        times = [(aware(r['timestamp']) - origin).total_seconds() / 3600 for r in train]
        logs = [log(r['value']) for r in train]
        mean_t, mean_y = sum(times) / len(times), sum(logs) / len(logs)
        variance = sum((t - mean_t)**2 for t in times)
        if variance <= 0:
            continue
        slope = sum((t - mean_t) * (y - mean_y) for t, y in zip(times, logs)) / variance
        for horizon in horizons_h:
            target_time = origin + timedelta(hours=horizon)
            candidates = [r for r in split['test'] if abs((aware(r['timestamp']) - target_time).total_seconds()) <= target_tolerance_h * 3600]
            if not candidates:
                continue
            target = min(candidates, key=lambda r: abs((aware(r['timestamp']) - target_time).total_seconds()))
            actual_horizon = (aware(target['timestamp']) - origin).total_seconds() / 3600
            key = (split['run_id'], split['segment_id'], split['origin'], target['evidence_id'])
            if key in seen:
                continue
            seen.add(key)
            for model, predicted in [('persistence', last['value']), ('training_log_linear', None)]:
                if model == 'training_log_linear':
                    log_value = log(last['value']) + slope * (actual_horizon + age)
                    if not -700 < log_value < 700:
                        blocked.append({'origin': split['origin'], 'reason': 'trend_overflow'})
                        continue
                    predicted = exp(log_value)
                result.append({'run_id': split['run_id'], 'segment_id': split['segment_id'],
                               'forecast_origin': split['origin'], 'timestamp': target['timestamp'],
                               'horizon_h': actual_horizon, 'requested_horizon_h': horizon,
                               'model': model, 'observed': target['value'], 'predicted': predicted,
                               'signed_gap': predicted - target['value'], 'absolute_error': abs(predicted-target['value']),
                               'observable': 'total_dry_residue_g_l', 'target_evidence_id': target['evidence_id'],
                               'input_evidence_ids': [r['evidence_id'] for r in train],
                               'input_availability_max': max(aware(r['available_at']) for r in train).isoformat(),
                               'training_only_effective_rate_h': slope if model == 'training_log_linear' else None,
                               'classification': 'predicted', 'interval': None,
                               'independent_validation': target.get('independent_assay', False)})
    grouped = defaultdict(list)
    for row in result:
        grouped[(row['run_id'], row['model'], row['requested_horizon_h'])].append(row)
    metrics = []
    for (run, model, horizon), group in grouped.items():
        # Point sample scores: separate from interval time-weighted productivity metrics.
        n = len(group)
        metrics.append({'run_id': run, 'model': model, 'horizon_h': horizon, 'count': n,
                        'point_bias': sum(r['signed_gap'] for r in group)/n,
                        'point_mae': sum(r['absolute_error'] for r in group)/n,
                        'point_rmse': sqrt(sum(r['signed_gap']**2 for r in group)/n),
                        'independent_assay_count': sum(r['independent_validation'] for r in group)})
    return {'predictions': result, 'metrics': metrics, 'blocked': blocked,
            'qualification': 'exploratory_baseline_backtest_on_available_residue_estimates',
            'configuration': {'horizons_h': list(horizons_h), 'minimum_training': minimum_training,
                              'training_window_h': training_window_h, 'max_data_age_h': max_data_age_h,
                              'target_tolerance_h': target_tolerance_h},
            'limitations': ['No model/calibration selection may use these test outcomes.',
                           'Overlapping rolling origins are correlated.',
                           'Shared OD calibration errors are not independent validation.',
                           'Mechanistic GEM and kinetic forecast qualification is separate.']}


def censored_interval_loss(prediction: float, lower: float | None, upper: float | None,
                           *, scale: float = 1.) -> float:
    """Squared distance outside censoring bounds, not loss against an invented midpoint."""
    if not isfinite(prediction) or not isfinite(scale) or scale <= 0:
        raise ValueError('finite prediction and positive uncertainty scale required')
    if lower is None and upper is None:
        raise ValueError('at least one censoring bound required')
    if lower is not None and not isfinite(lower) or upper is not None and not isfinite(upper):
        raise ValueError('finite censoring bounds required')
    if lower is not None and upper is not None and lower > upper:
        raise ValueError('censoring bounds reversed')
    distance = max(0., (lower-prediction) if lower is not None else 0.,
                   (prediction-upper) if upper is not None else 0.)
    return (distance/scale)**2
