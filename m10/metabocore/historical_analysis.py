"""Source-linked historical residue calculations, not cellular growth inference."""
from __future__ import annotations
from collections import defaultdict, Counter
from datetime import datetime
from math import isfinite
from typing import Mapping, Sequence

VERSION = 'historical-residue-1.0'


def _dt(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.utcoffset() is None:
        raise ValueError('timezone-aware observation time required')
    return dt


def _value(row):
    return row.get('value', row.get('normalized_value'))


def _time(row):
    return row.get('event_time') or row.get('event_timestamp') or row.get('timestamp')


def _good(row):
    value = _value(row)
    return (row.get('accepted', True) and value is not None and isinstance(value, (int, float))
            and not isinstance(value, bool) and isfinite(value) and value >= 0 and _time(row) is not None
            and row.get('classification') in {'measured', 'source-derived', 'recalculated'})


def _lineage(rows):
    return {'parent_observation_ids': [r['observation_id'] for r in rows],
            'source_locators': [r.get('source_locator') for r in rows],
            'input_qc_flags': sorted({f for r in rows for f in r.get('qc_flags', [])})}


def _availability(rows):
    times = [r.get('availability_time') or r.get('availability_timestamp') for r in rows]
    return max(times, key=_dt) if all(times) else None


def analyze_observations(observations: Sequence[Mapping], *, authoritative_volume_l: float = 10.,
                         max_gap_h: float = 4., residue_parameter: str = 'dry_residue_g_L',
                         calibration_intervals: Mapping | None = None) -> dict:
    """Algebraic residue accumulation and source-derived D*X proxy on observed rows.

    D is user-confirmed dilution [h^-1], but historical delivery/outflow still needs
    validation. Exact-time pairing only; no nearest assay or fill. Calibration
    interval propagation assumes one completely shared multiplicative coefficient
    and does not estimate total uncertainty or independent measurement confidence.
    """
    if not isfinite(authoritative_volume_l) or authoritative_volume_l <= 0 or not isfinite(max_gap_h) or max_gap_h <= 0:
        raise ValueError('positive volume and maximum gap required')
    calibration_intervals = calibration_intervals or {}
    ids = [r.get('observation_id') for r in observations]
    if any(x is None for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('unique nonmissing observation IDs required for evidence lineage')
    residue_rows = [r for r in observations if r.get('parameter_code') == residue_parameter]
    exclusions, groups, points = [], defaultdict(list), []
    all_by_time = defaultdict(list)
    for row in observations:
        if _time(row):
            all_by_time[(row.get('run_id'), row.get('segment_id'), _time(row))].append(row)
    for row in residue_rows:
        reason = None
        if not _good(row):
            reason = 'rejected_or_missing_residue_point'
        elif row.get('unit', row.get('normalized_unit')) != 'g/L':
            reason = 'residue_unit_not_g_per_litre'
        elif row.get('segment_id') is None:
            reason = 'segment_identity_unknown'
        elif row.get('calibration_version') is None and row.get('classification') != 'measured':
            reason = 'derived_residue_calibration_unknown'
        if reason:
            exclusions.append({'parent_observation_ids': [row['observation_id']], 'reason': reason})
            continue
        _dt(_time(row))
        points.append(row)
        groups[(row.get('run_id'), row['segment_id'], row.get('calibration_version'))].append(row)
    intervals, proxies, comparisons = [], [], []
    for (run, segment, calibration), rows in groups.items():
        rows = sorted(rows, key=lambda r: _dt(_time(r)))
        # Multiple residues at one timestamp need an explicit selection/replicate policy.
        counts = Counter(_time(r) for r in rows)
        unique = [r for r in rows if counts[_time(r)] == 1]
        for row in rows:
            if counts[_time(row)] > 1:
                exclusions.append({'parent_observation_ids': [row['observation_id']], 'reason': 'duplicate_residue_timestamp'})
        for start, end in zip(unique, unique[1:]):
            dt = (_dt(_time(end)) - _dt(_time(start))).total_seconds() / 3600
            if dt <= 0 or dt > max_gap_h:
                exclusions.append({'parent_observation_ids': [start['observation_id'], end['observation_id']],
                                   'reason': 'nonpositive_or_excessive_interval', 'elapsed_h': dt})
                continue
            intervening = [r for r in residue_rows if r.get('run_id') == run and r.get('segment_id') == segment
                           and _time(r) and _dt(_time(start)) < _dt(_time(r)) < _dt(_time(end))]
            if intervening:
                exclusions.append({'parent_observation_ids': [start['observation_id'], end['observation_id']]
                                   + [r['observation_id'] for r in intervening],
                                   'reason': 'intervening_rejected_duplicate_or_other_calibration_point'})
                continue
            delta_x = _value(end) - _value(start)
            rate = authoritative_volume_l * delta_x / dt
            row = {'run_id': run, 'segment_id': segment, 'interval_start': _time(start), 'interval_end': _time(end),
                   'elapsed_h': dt, 'volume_l': authoritative_volume_l,
                   'volume_basis': 'user_authoritative_constant_10L' if authoritative_volume_l == 10 else 'explicit_constant_volume_scenario',
                   'endpoint': 'total_dry_residue', 'start_g_l': _value(start), 'end_g_l': _value(end),
                   'net_inventory_accumulation_g_h': rate, 'concentration_change_g_l_h': delta_x/dt,
                   'net_biological_formation_g_l_h': None,
                   'formation_blocker': 'verified liquid/solid addition and removal streams required',
                   'classification': 'recalculated', 'status': 'calibration_dependent_reconstruction',
                   'calibration_version': calibration, 'availability_time': _availability([start,end]),
                   'uncertainty': None, 'equation_version': VERSION, **_lineage([start,end])}
            c = calibration_intervals.get(calibration)
            if c:
                k, limits = c['coefficient'], c['coefficient_interval']
                if not (isfinite(k) and k > 0 and len(limits) == 2 and all(isfinite(q) for q in limits) and 0 < limits[0] <= limits[1]):
                    raise ValueError('invalid shared multiplicative calibration interval')
                bounds = sorted(rate * q / k for q in limits)
                row['uncertainty'] = {'lower_g_h': bounds[0], 'upper_g_h': bounds[1],
                                      'kind': 'shared_coefficient_only_interval',
                                      'coefficient_source': c.get('source'),
                                      'assumption': 'same multiplicative calibration error at both endpoints',
                                      'excludes': ['OD noise', 'sample variation', 'volume uncertainty', 'noncellular residue changes'],
                                      'not_total_prediction_interval': True}
            intervals.append(row)
        for residue in unique:
            peers = all_by_time[(run, segment, _time(residue))]
            dilution = [r for r in peers if r.get('parameter_code') == 'legacy_dilution_h_inv' and _good(r)
                        and r.get('unit',r.get('normalized_unit')) in {'1/h','h^-1'}]
            if len(dilution) == 1:
                d = dilution[0]
                proxy = _value(d) * _value(residue)
                proxies.append({'run_id': run, 'segment_id': segment, 'event_time': _time(residue),
                                'residue_g_l': _value(residue), 'dilution_h_inv': _value(d),
                                'dilution_residue_proxy_g_l_h': proxy, 'endpoint': 'total_dry_residue',
                                'classification': 'recalculated', 'status': 'conditional_proxy',
                                'calibration_version': calibration, 'availability_time': _availability([residue,d]),
                                'assumptions': ['D calculation reflects actual nonselective outflow / working volume',
                                                'sterile feed', 'steady inventory only if interpreted as net formation'],
                                'not_measured_harvest_or_biological_formation': True,
                                'uncertainty': None, 'equation_version': VERSION, **_lineage([residue,d])})
            else:
                exclusions.append({'parent_observation_ids':[residue['observation_id']],
                                   'reason':'missing_or_nonunique_exact_time_dilution'})
            for peer in peers:
                code = peer.get('parameter_code')
                if code == 'legacy_asv_g_L' and _good(peer) and peer.get('unit',peer.get('normalized_unit')) == 'g/L':
                    comparisons.append({'run_id': run, 'segment_id': segment, 'event_time': _time(residue),
                                        'selected_residue_g_l': _value(residue), 'legacy_asv_g_l': _value(peer),
                                        'selected_minus_legacy_g_l': _value(residue)-_value(peer),
                                        'legacy_over_selected': _value(peer)/_value(residue) if _value(residue)>1e-9 else None,
                                        'classification':'recalculated', 'status':'competing_derived_channels',
                                        'not_independent_validation':True,
                                        'calibration_version':calibration, **_lineage([residue,peer])})
    def span(values):
        return {'minimum':min(values),'maximum':max(values)} if values else None
    return {'residue_intervals': intervals, 'dilution_productivity_proxies': proxies,
            'legacy_comparisons': comparisons, 'exclusions': exclusions,
            'summary': {'residue_input_count':len(residue_rows),'eligible_residue_point_count':len(points),
                        'inventory_interval_count':len(intervals),'dilution_proxy_count':len(proxies),
                        'legacy_comparison_count':len(comparisons),
                        'positive_inventory_interval_count':sum(r['net_inventory_accumulation_g_h']>0 for r in intervals),
                        'negative_inventory_interval_count':sum(r['net_inventory_accumulation_g_h']<0 for r in intervals),
                        'inventory_accumulation_g_h_range':span([r['net_inventory_accumulation_g_h'] for r in intervals]),
                        'dilution_proxy_g_l_h_range':span([r['dilution_residue_proxy_g_l_h'] for r in proxies]),
                        'legacy_over_selected_range':span([r['legacy_over_selected'] for r in comparisons if r['legacy_over_selected'] is not None]),
                        'exclusion_counts':dict(Counter(r['reason'] for r in exclusions))},
            'configuration': {'residue_parameter':residue_parameter,'authoritative_volume_l':authoritative_volume_l,
                              'max_gap_h':max_gap_h,'joining':'exact event time/run/segment only'},
            'qualification':'observed-source algebraic reconstruction; not forecast evaluation',
            'limitations':['No interval is claimed as net biological formation without verified streams.',
                           'D*residue is a conditional dilution proxy, not measured harvest.',
                           'Shared calibration uncertainty does not make derived channels independent.',
                           'No interpolation across segment/calibration boundaries or long gaps.'],
            'equation_version':VERSION}


def build_hypotheses(run: Mapping) -> list[dict]:
    """Traceable diagnostic review order, never an inferred causal ranking.

    Evidence examples are deterministically capped, with total counts retained;
    missing evidence does not become support. IDs refer to imported source objects.
    """
    observations = run.get('observations', [])
    events = run.get('events', [])
    def select(predicate):
        return [r for r in observations if predicate(r)]
    def code(row):
        return str(row.get('parameter_code','')).lower()
    def flags(row):
        return set(row.get('qc_flags',[]))
    def refs(rows, limit=30):
        return [{'observation_id':r['observation_id'],'parameter_code':r.get('parameter_code'),
                 'event_time':_time(r),'source_locator':r.get('source_locator'),'qc_flags':r.get('qc_flags',[])}
                for r in rows[:limit]]
    def event_refs(rows, limit=12):
        return [{'event_id':r.get('event_id'),'event_time':r.get('event_time'),
                 'source_locator':r.get('source_locator'),'source_span':r.get('description'),
                 'review_state':r.get('review_state')} for r in rows[:limit]]
    calibration=select(lambda r: code(r) in {'dry_residue_g_l','legacy_asv_g_l'}
                       or any('calibration' in f for f in flags(r)))
    delivery=select(lambda r: 'negative_inferred_delivery' in flags(r)
                    or 'bottle_mass' in code(r) or code(r) in {'legacy_feed_ml_min','legacy_total_liquid_ml_min'})
    gasqc=select(lambda r: code(r).startswith('offgas_') and bool(flags(r)&{'invalid_gas_composition_sum','outside_physical_range','nonfinite','spreadsheet_error'}))
    gas=select(lambda r: code(r).startswith(('offgas_','inlet_')))
    nutrients=select(lambda r: r.get('matrix') in {'medium','titrant','ammonia_titrant','koh_titrant','concentrate','trace_stock'}
                     or any(p in code(r) for p in ('nh3','nh4','po4','ammon','phosph','phosphate','nitrogen','nutrient')))
    nutrients.sort(key=lambda r: 'censored' not in flags(r))
    metals=select(lambda r: any(p in code(r) for p in ('copper','iron','cu_', 'fe_', 'cu2','fe2'))
                  or code(r) in {'cu','fe'} or any(p in str(r.get('basis','')).lower() for p in ('cuso4','feso4','copper','iron')))
    oxygen=select(lambda r: code(r) in {'do_pct','rpm','temperature_c','inlet_air_l_min','inlet_o2_l_min'})
    morphology=select(lambda r: any(p in code(r) for p in ('morph','cocci','producer','microscop')))
    candidates=[
        ('calibration','Measurement / calibration differences',calibration,[],
         'Optical scattering, calibration transfer or noncellular solids can change residue estimates.',
         'Sample-matched OD and independent residue assays disagree after method and dilution reconciliation.',
         ['The selected endpoint is total dry residue; no direction of cellular bias is established.'],
         ['Instrument/path/dilution changes','Shared calibration coefficient','Medium solids'],
         ['Matched assay method and reporting time','Biological-sample replicate structure'],
         'Compare paired existing OD and gravimetry by sample, instrument and calibration version.'),
        ('delivery','Delivery and bottle interpretation',delivery,[e for e in events if 'bottle' in str(e.get('kind',''))],
         'Bottle resets, uncertain density or interrupted delivery can decouple commands and actual supply.',
         'Mass changes align with bottle events or commanded versus delivered-flow discrepancies.',
         ['A negative weight difference can represent a bottle replacement rather than reverse delivery.'],
         ['Spills/evaporation','Tare changes','Preparation time differs from connection time'],
         ['Verified connection intervals','Density and pump/scale calibration'],
         'Reconcile existing bottle labels, replacement records and scale trajectories.'),
        ('gas_qc','Gas measurement and exhaust closure',gasqc or gas,[],
         'Channel calibration, basis or delay can produce apparent gas imbalance.',
         'Invalid composition sums or synchronized-flow contradictions persist after documented calibration checks.',
         ['Valid arithmetic composition alone does not validate channel identity, wet/dry basis or exhaust flow.'],
         ['Unknown analyzer lag','Unmeasured exhaust','Concentrator impurities','Possible nitrogen exchange'],
         ['Gas channel definitions and calibration','Independent exhaust closure','Meter standard conditions'],
         'Audit source gas channels, reference conditions and existing calibration/delay evidence.'),
        ('nutrients','N/P availability and unresolved sinks',nutrients,[],
         'Supply, residual inventory and nonbiological sinks may explain apparent nutrient disappearance.',
         'Element-specific input and inventory changes support the same interpretation on matched intervals.',
         ['Residual concentration and undated preparation entries do not identify cellular uptake.'],
         ['Censored assays','Precipitation/adsorption','Titrant N','Nitrogen stripping or conversion'],
         ['Dated recipe/use links','Verified delivered quantities','Matrix-specific assays'],
         'Reconcile existing batches, use records and censored broth assays on an elemental basis.'),
        ('metals','Cu/Fe exposure and measurement basis',metals,[],
         'Metal availability or exposure may affect activity, conditional on verified chemical and biological evidence.',
         'Independent matched metal assays and exposure histories support reproducible response differences.',
         ['Total metal concentration is not free-ion activity; GEM bounds do not model toxicity or regulation.'],
         ['Precipitation/complexation','Matrix recovery','Run-specific physiology','Sparse sampling'],
         ['Matrix-specific assay validation','Dated exposure history','Independent biological response'],
         'Compare existing Cu/Fe assay metadata and exposure timing before attributing a growth effect.'),
        ('oxygen','Oxygen transfer versus changing uptake',oxygen,[],
         'A DO excursion may reflect changing transfer, demand or measurement response.',
         'Lagged DO/RPM/inlet changes can be compared with independent biomass and uptake evidence.',
         ['High DO by itself does not establish oxygen toxicity; declining uptake can also raise DO.'],
         ['Temperature/pressure','Antifoam and geometry','Uncertain solubility','Probe response'],
         ['Matched broth transfer conditions','Calibrated oxygen concentration reference','Independent uptake'],
         'Compare existing event-aligned DO and gas records without converting a rise directly into a causal diagnosis.'),
        ('composition','Morphology and culture composition',morphology,[],
         'Aggregation and community changes can affect optical scattering and total-residue interpretation.',
         'Time-linked images and count methodology support reproducible morphotype differences.',
         ['Morphotype counts do not establish species identity or biomass fractions.'],
         ['Sampling/field selection','Unknown scale/magnification','Dead material','Scattering changes'],
         ['Image-to-sample/time/scale links','Counting protocol','Independent identity evidence'],
         'Link available images and count records to samples before comparing biological interpretations.'),
        ('history','Process history and recovery',[],[e for e in events if e.get('boundary')],
         'Inoculation, withdrawal/refill, technical faults or recovery changes can alter inventory trajectories.',
         'Source-documented events coincide with discrete inventory or measurement-regime changes.',
         ['Temporal coincidence alone does not separate biological change from altered volume or measurement.'],
         ['Unmeasured event volumes','Uncertain start/end times','Multiple simultaneous interventions'],
         ['Integrated event additions/removals','Harvest/recovery records','Timing uncertainty'],
         'Review existing event spans and inventory accounting before fitting a change in growth.')]
    result=[]
    for rank,(key,title,obs,ev,mechanism,signature,contradiction,confounders,missing,next_check) in enumerate(candidates,1):
        result.append({'hypothesis_id':f'{run.get("run_id","run")}:hypothesis:{key}',
                       'candidate':title,'diagnostic_review_order':rank,
                       'ordering_meaning':'measurement and identifiability review order; not a causal probability ranking',
                       'proposed_mechanism':mechanism,'expected_signature':signature,
                       'supporting_evidence':refs(obs),'supporting_event_evidence':event_refs(ev),
                       'parent_observation_ids':[r['observation_id'] for r in obs[:30]],
                       'parent_event_ids':[r.get('event_id') for r in ev[:12]],
                       'available_observation_count':len(obs),'available_event_count':len(ev),
                       'evidence_selection':'first 30 imported matching observations and 12 matching events; counts include all matches',
                       'evidence_interpretation':'records motivate checking this alternative; they do not establish the proposed cause',
                       'contradicting_or_non_supporting_evidence':contradiction,'confounders':confounders,
                       'missing_measurements':missing,'model_sensitivity':None,
                       'confidence':'unresolved' if obs or ev else 'no_linked_evidence',
                       'next_analytical_check':next_check,'researcher_review':'pending'})
    return result
