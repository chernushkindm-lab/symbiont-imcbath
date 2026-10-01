"""Explicit, constant-volume dynamic FBA replay with a nitrogen ledger.

The input is a normalized experiment description, not a workbook parser.  All
physical quantities carry units and provenance; observations never alter state.
"""
from __future__ import annotations

from bisect import bisect_right
from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any, Callable, Mapping

_PROVENANCE = {"measured", "derived", "synthetic"}
_TIME_TOL = 1e-12
_ROUND_OFF = 1e-10
_GASES = {"ch4": "EX_ch4_e", "o2": "EX_o2_e"}


def _object(value: Any, path: str, required: set[str], optional: set[str] | None = None) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path}: expected an object")
    missing = required - value.keys()
    extra = value.keys() - required - (optional or set())
    if missing:
        raise ValueError(f"{path}: missing fields {sorted(missing)}")
    if extra:
        raise ValueError(f"{path}: unknown fields {sorted(extra)}")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: expected nonempty text")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{path}: expected a finite number")
    return float(value)


def _quantity(value: Any, unit: str, path: str, *, positive: bool = False, maximum: float | None = None) -> float:
    q = _object(value, path, {"value", "unit", "provenance", "source"}, {"note"})
    if q["unit"] != unit:
        raise ValueError(f"{path}: expected unit {unit!r}, received {q['unit']!r}; convert explicitly upstream")
    if not isinstance(q["provenance"], str) or q["provenance"] not in _PROVENANCE:
        raise ValueError(f"{path}: provenance must be measured, derived, or synthetic")
    _text(q["source"], f"{path}.source")
    if "note" in q:
        _text(q["note"], f"{path}.note")
    result = _number(q["value"], f"{path}.value")
    if result < 0 or (positive and result == 0):
        raise ValueError(f"{path}: expected a {'positive' if positive else 'nonnegative'} value")
    if maximum is not None and result > maximum:
        raise ValueError(f"{path}: value must be at most {maximum}")
    return result


def _list(value: Any, path: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected a list")
    return value


@dataclass(frozen=True)
class _Interval:
    start: float
    end: float
    volume: float
    liquid_rate: float
    nitrogen_rate: float
    gas_rates: dict[str, float]


@dataclass(frozen=True)
class _Input:
    source: dict
    step: float
    start: float
    biomass: float
    nitrogen: float
    volume: float
    intervals: list[_Interval]
    boluses: list[tuple[float, float, str]]
    observations: list[dict]


def _normalize(document: Mapping[str, Any]) -> _Input:
    d = _object(document, "input", {"schema_version", "time_step", "gas_basis", "initial", "intervals", "boluses"},
                {"label", "description", "observations"})
    if type(d["schema_version"]) is not int or d["schema_version"] != 1:
        raise ValueError("schema_version: only integer version 1 is supported")
    for key in ("label", "description"):
        if key in d:
            _text(d[key], key)
    step = _quantity(d["time_step"], "h", "time_step", positive=True)
    basis = _object(d["gas_basis"], "gas_basis", {"molar_volume", "reference_conditions"})
    molar_volume = _quantity(basis["molar_volume"], "L/mol", "gas_basis.molar_volume", positive=True)
    _text(basis["reference_conditions"], "gas_basis.reference_conditions")
    initial = _object(d["initial"], "initial", {"time", "biomass", "nitrogen", "volume"})
    start = _quantity(initial["time"], "h", "initial.time")
    biomass = _quantity(initial["biomass"], "g_model_biomass/L", "initial.biomass", positive=True)
    nitrogen = _quantity(initial["nitrogen"], "mmol_N/L", "initial.nitrogen")
    volume = _quantity(initial["volume"], "L", "initial.volume", positive=True)
    if not all(math.isfinite(value) for value in (biomass * volume, nitrogen * volume)):
        raise ValueError("initial: derived biomass or nitrogen amount is nonfinite")
    intervals = []
    expected_start = start
    for i, raw in enumerate(_list(d["intervals"], "intervals")):
        path = f"intervals[{i}]"
        item = _object(raw, path, {"start", "end", "volume", "gas_streams", "liquid_feeds"}, {"label"})
        begin = _quantity(item["start"], "h", path + ".start")
        end = _quantity(item["end"], "h", path + ".end")
        actual_volume = _quantity(item["volume"], "L", path + ".volume", positive=True)
        if not math.isclose(begin, expected_start, rel_tol=0, abs_tol=_TIME_TOL):
            raise ValueError(f"{path}: intervals must be ordered, contiguous, and begin at initial.time")
        if end - begin <= _TIME_TOL:
            raise ValueError(f"{path}: end must be greater than start")
        if not math.isclose(actual_volume, volume, rel_tol=0, abs_tol=_TIME_TOL):
            raise ValueError(f"{path}.volume: variable-volume replay is unsupported; use a constant-volume window")
        gas_rates = {key: 0.0 for key in _GASES}
        for j, raw_stream in enumerate(_list(item["gas_streams"], path + ".gas_streams")):
            sp = f"{path}.gas_streams[{j}]"
            stream = _object(raw_stream, sp, {"name", "flow", "mole_fractions", "availability_fractions"})
            _text(stream["name"], sp + ".name")
            flow = _quantity(stream["flow"], "L/min", sp + ".flow")
            fractions = _object(stream["mole_fractions"], sp + ".mole_fractions", set(_GASES))
            efficiencies = _object(stream["availability_fractions"], sp + ".availability_fractions", set(_GASES))
            total_fraction = 0.0
            for gas in _GASES:
                fraction = _quantity(fractions[gas], "1", sp + f".mole_fractions.{gas}", maximum=1)
                available = _quantity(efficiencies[gas], "1", sp + f".availability_fractions.{gas}", maximum=1)
                total_fraction += fraction
                gas_rates[gas] += available * fraction * flow * 60 * 1000 / molar_volume
            if total_fraction > 1 + _ROUND_OFF:
                raise ValueError(f"{sp}: methane and oxygen mole fractions exceed one")
        liquid_rate = nitrogen_rate = 0.0
        for j, raw_feed in enumerate(_list(item["liquid_feeds"], path + ".liquid_feeds")):
            fp = f"{path}.liquid_feeds[{j}]"
            feed = _object(raw_feed, fp, {"name", "flow", "nitrogen_concentration"})
            _text(feed["name"], fp + ".name")
            flow = _quantity(feed["flow"], "L/h", fp + ".flow")
            concentration = _quantity(feed["nitrogen_concentration"], "mmol_N/L", fp + ".nitrogen_concentration")
            liquid_rate += flow
            nitrogen_rate += flow * concentration
        derived = [liquid_rate, nitrogen_rate, *gas_rates.values(), liquid_rate / volume]
        if not all(math.isfinite(x) for x in derived):
            raise ValueError(f"{path}: derived delivery rate is nonfinite")
        intervals.append(_Interval(begin, end, actual_volume, liquid_rate, nitrogen_rate, gas_rates))
        expected_start = end
    if not intervals:
        raise ValueError("intervals: at least one interval is required")
    boluses = []
    for i, raw in enumerate(_list(d["boluses"], "boluses")):
        path = f"boluses[{i}]"
        event = _object(raw, path, {"time", "nitrogen_amount", "label", "negligible_volume"})
        time = _quantity(event["time"], "h", path + ".time")
        amount = _quantity(event["nitrogen_amount"], "mmol_N", path + ".nitrogen_amount")
        if not math.isfinite(amount / volume):
            raise ValueError(f"{path}: derived concentration increment is nonfinite")
        label = _text(event["label"], path + ".label")
        if event["negligible_volume"] is not True:
            raise ValueError(f"{path}: solute-pulse model requires an explicit negligible_volume=true assumption")
        if not start <= time <= expected_start:
            raise ValueError(f"{path}: event must lie within the replay window; earlier additions belong in initial.nitrogen")
        boluses.append((time, amount, label))
    boluses.sort(key=lambda event: event[0])
    maximum_nitrogen_amount = nitrogen * volume + sum(event[1] for event in boluses)
    maximum_nitrogen_amount += sum(interval.nitrogen_rate * (interval.end - interval.start) for interval in intervals)
    if not math.isfinite(maximum_nitrogen_amount) or not math.isfinite(maximum_nitrogen_amount / volume):
        raise ValueError("input: total declared nitrogen input or corresponding concentration is nonfinite")
    observations = []
    for i, raw in enumerate(_list(d.get("observations", []), "observations")):
        path = f"observations[{i}]"
        obs = _object(raw, path, {"time"}, {"biomass", "nitrogen", "label"})
        time = _quantity(obs["time"], "h", path + ".time")
        if not start <= time <= expected_start:
            raise ValueError(f"{path}: observation must lie within the replay window")
        converted = {"time_h": time}
        for key, unit in (("biomass", "g_model_biomass/L"), ("nitrogen", "mmol_N/L")):
            if key in obs:
                converted[key] = _quantity(obs[key], unit, path + "." + key)
        if len(converted) == 1:
            raise ValueError(f"{path}: at least one observed quantity is required")
        if "label" in obs:
            converted["label"] = _text(obs["label"], path + ".label")
        observations.append(converted)
    return _Input(deepcopy(dict(document)), step, start, biomass, nitrogen, volume, intervals, boluses, observations)


def _registry(value: Any, path: str = "") -> list[dict]:
    if isinstance(value, Mapping):
        if {"value", "unit", "provenance", "source"} <= value.keys():
            return [{"path": path, **dict(value)}]
        return [entry for key, child in value.items() for entry in _registry(child, f"{path}.{key}".strip("."))]
    if isinstance(value, list):
        return [entry for i, child in enumerate(value) for entry in _registry(child, f"{path}[{i}]")]
    return []


def _audit_nitrogen_sources(model: Any) -> dict:
    """Reject untracked nitrogen input; never change the caller's medium.

    For a boundary metabolite with stoichiometric coefficient ``s``, ``s*v >
    0`` supplies material to the modeled system. This handles either exchange
    orientation and also checks reversible demand/sink sources when present.
    """
    if model is None:
        return {"status": "not_performed", "reason": "injected test solver without a model; no model-source claim is made"}
    if not hasattr(model, "exchanges") or not hasattr(model, "reactions"):
        raise ValueError("replay model must expose reactions and exchanges for nitrogen-source validation")
    try:
        ammonium = model.reactions.get_by_id("EX_nh4_e")
    except (AttributeError, KeyError) as error:
        raise ValueError("replay requires the canonical EX_nh4_e ammonium exchange") from error
    entries = list(ammonium.metabolites.items())
    if len(entries) != 1 or entries[0][1] != -1 or entries[0][0].elements.get("N", 0) != 1:
        raise ValueError("EX_nh4_e must exchange one N atom per flux unit with stoichiometric coefficient -1; the nitrogen ledger cannot interpret an altered exchange")
    reactions = {reaction.id: reaction for reaction in model.exchanges}
    exchange_ids = set(reactions)
    # Reversible intracellular sinks can supply N just as an exchange can.
    for reaction in getattr(model, "boundary", []):
        reactions[reaction.id] = reaction
    forbidden = []
    unknown = []
    nitrogen_boundaries = []
    boundary_details = []
    for reaction in reactions.values():
        if reaction.id == "EX_nh4_e":
            continue
        nitrogen_metabolites = []
        for metabolite, coefficient in reaction.metabolites.items():
            import_allowed = ((coefficient < 0 and reaction.lower_bound < 0)
                              or (coefficient > 0 and reaction.upper_bound > 0))
            elements = metabolite.elements
            if import_allowed and not elements:
                unknown.append(f"{reaction.id} ({metabolite.id}: missing elemental formula)")
            elif elements.get("N", 0) > 0:
                nitrogen_boundaries.append(reaction.id)
                nitrogen_metabolites.append({"metabolite_id": metabolite.id, "formula": metabolite.formula,
                                             "nitrogen_atoms": elements["N"], "stoichiometric_coefficient": coefficient,
                                             "import_direction_open": import_allowed})
                if import_allowed:
                    forbidden.append(reaction.id)
        if nitrogen_metabolites:
            boundary_details.append({"reaction_id": reaction.id,
                                     "kind": "exchange" if reaction.id in exchange_ids else "other_boundary",
                                     "lower_bound": reaction.lower_bound, "upper_bound": reaction.upper_bound,
                                     "nitrogen_metabolites": nitrogen_metabolites})
    if forbidden or unknown:
        details = ", ".join(sorted(set(forbidden + unknown)))
        raise ValueError(
            "Ammonium-only replay rejects open non-ammonium nitrogen sources or unverified source formulas: "
            f"{details}. Apply an explicit ammonium-only model/profile (for example symbiont-reference), "
            "closing those import directions; replay does not silently modify the model medium."
        )
    return {"status": "passed", "tracked_source": "EX_nh4_e",
            "other_nitrogen_boundary_imports": "closed",
            "checked_nitrogen_boundaries": sorted(set(nitrogen_boundaries)),
            "boundary_details": sorted(boundary_details, key=lambda item: item["reaction_id"]),
            "basis": "metabolite N atom counts, boundary stoichiometry and allowed flux directions"}


def _compare(observations: list[dict], states: list[dict]) -> list[dict]:
    """Interpolate after simulation; observation timestamps never split steps."""
    times = [state["time_h"] for state in states]
    comparisons = []
    for obs in observations:
        time = obs["time_h"]
        record = {**obs, "use": "withheld_comparison_only"}
        if time > times[-1] + _TIME_TOL:
            record["status"] = "outside_completed_window"
        else:
            index = max(0, bisect_right(times, time) - 1)
            left = states[index]
            right = states[min(index + 1, len(states) - 1)]
            width = right["time_h"] - left["time_h"]
            weight = (time - left["time_h"]) / width if width > _TIME_TOL else 0.0
            record["status"] = "compared"
            record["prediction_method"] = "state_or_linear_interpolation; exact_event_times_use_post_bolus_state"
            for key, field in (("biomass", "biomass_g_model_L"), ("nitrogen", "nitrogen_mmol_N_L")):
                if key in obs:
                    predicted = left[field] + weight * (right[field] - left[field])
                    record[f"predicted_{key}"] = predicted
                    record[f"residual_{key}"] = predicted - obs[key]
        comparisons.append(record)
    return comparisons


def replay_document(document: Mapping[str, Any], model: Any = None, *, solve_fn: Callable | None = None,
                    method: str = "pfba") -> dict[str, Any]:
    """Replay a validated JSON document, stopping on infeasible/invalid solves.

    Pass an explicitly configured ammonium-only model to select a profile.
    The unchanged default baseline is rejected because nitrate import is open.
    ``solve_fn`` is a test seam with the same signature as core.solve; using a
    stub with model=None marks the model-source audit as not performed.
    Invalid input raises ValueError before any model is loaded or solver called.
    """
    data = _normalize(document)
    if method not in {"fba", "pfba"}:
        raise ValueError("method must be fba or pfba")
    if solve_fn is None:
        from .core import load_baseline, solve
        solve_fn = solve
        if model is None:
            model = load_baseline()
    nitrogen_source_audit = _audit_nitrogen_sources(model)
    t, x, n, volume = data.start, data.biomass, data.nitrogen, data.volume
    ledger = {"initial_mmol_N": n * volume, "continuous_feed_mmol_N": 0.0,
              "bolus_mmol_N": 0.0, "net_cellular_removal_mmol_N": 0.0,
              "dilution_removal_mmol_N": 0.0, "roundoff_adjustment_mmol_N": 0.0}
    states: list[dict] = []
    steps: list[dict] = []
    events: list[dict] = []
    next_event = 0
    result: dict[str, Any] = {
        "schema_version": 1, "status": "completed", "method": method,
        "label": data.source.get("label", "unnamed replay"),
        "input": data.source, "quantity_registry": _registry(data.source),
        "model_provenance": deepcopy(getattr(model, "_symbiont_provenance", {"status": "untracked_model"})),
        "nitrogen_source_audit": nitrogen_source_audit,
        "states": states, "steps": steps, "bolus_events": events,
        "assumptions": ["constant, perfectly mixed volume; liquid outflow equals total liquid inflow",
                        "no biomass decay, retention, uptake kinetics, or gas-transfer dynamics",
                        "gas mole fractions share the declared volume reference basis; unlisted gas fraction is inert",
                        "boluses are instantaneous nitrogen additions with negligible volume",
                        "upstream nominal model-biomass units; no biomass normalization correction",
                        "all later observations are withheld; numerical replay is not biological validation"],
    }

    def record_state(kind: str) -> None:
        expected = (ledger["initial_mmol_N"] + ledger["continuous_feed_mmol_N"] + ledger["bolus_mmol_N"]
                    - ledger["net_cellular_removal_mmol_N"] - ledger["dilution_removal_mmol_N"]
                    + ledger["roundoff_adjustment_mmol_N"])
        states.append({"time_h": t, "biomass_g_model_L": x, "nitrogen_mmol_N_L": n,
                       "volume_L": volume, "kind": kind,
                       "nitrogen_ledger": {**ledger, "inventory_mmol_N": n * volume,
                                           "closure_error_mmol_N": n * volume - expected}})

    def apply_events() -> None:
        nonlocal n, next_event
        while next_event < len(data.boluses) and abs(data.boluses[next_event][0] - t) <= _TIME_TOL:
            event_time, amount, label = data.boluses[next_event]
            n += amount / volume
            ledger["bolus_mmol_N"] += amount
            events.append({"time_h": event_time, "nitrogen_amount_mmol_N": amount, "label": label})
            next_event += 1
            record_state("post_bolus")

    def stop(reason: str, solver_status: str | None = None) -> dict:
        result.update(status="stopped", stopped_at_time_h=t, reason=reason, solver_status=solver_status)
        result["observation_comparisons"] = _compare(data.observations, states)
        return result

    record_state("initial")
    apply_events()
    for interval_index, interval in enumerate(data.intervals):
        dilution = interval.liquid_rate / interval.volume
        while t < interval.end - _TIME_TOL:
            stop_time = min(interval.end, t + data.step)
            if dilution > 0:
                stop_time = min(stop_time, t + 0.5 / dilution)
            if next_event < len(data.boluses):
                stop_time = min(stop_time, data.boluses[next_event][0])
            dt = stop_time - t
            if dt <= 0 or not math.isfinite(dt):
                return stop("time step cannot advance at this numerical precision")
            if x <= 0 or not math.isfinite(x):
                return stop("biomass became nonpositive or nonfinite")
            nitrogen_available = n / dt + interval.nitrogen_rate / volume - dilution * n
            if nitrogen_available < -_ROUND_OFF:
                return stop("negative nitrogen availability before solve")
            caps = {reaction: interval.gas_rates[gas] / (volume * x) for gas, reaction in _GASES.items()}
            caps["EX_nh4_e"] = max(0.0, nitrogen_available) / x
            if not all(math.isfinite(cap) for cap in caps.values()):
                return stop("derived uptake cap is nonfinite")
            solution = solve_fn(model, method=method, uptake_caps=caps)
            if solution.get("status") != "optimal":
                return stop("GEM solve did not return an optimal solution; no failed step was applied", solution.get("status"))
            if solution.get("numerically_feasible") is False:
                return stop("GEM flux vector failed numerical mass-balance or bound checks; no failed step was applied", solution.get("status"))
            try:
                mu = _number(solution.get("growth_rate_h"), "solver.growth_rate_h")
                qn = -_number(solution["fluxes"]["EX_nh4_e"], "solver.fluxes.EX_nh4_e")
            except (ValueError, KeyError, TypeError) as error:
                return stop(f"invalid solver output: {error}", solution.get("status"))
            if mu < -_ROUND_OFF or qn > caps["EX_nh4_e"] + 1e-7:
                return stop("solver returned negative growth or violated the nitrogen uptake cap", solution.get("status"))
            feed_n = interval.nitrogen_rate * dt
            cellular_n = qn * x * volume * dt
            dilution_n = dilution * n * volume * dt
            new_n = n + (feed_n - cellular_n - dilution_n) / volume
            new_x = x + (mu - dilution) * x * dt
            if not math.isfinite(new_x) or not math.isfinite(new_n) or new_x <= 0:
                return stop("state update produced nonfinite or nonpositive biomass / nonfinite nitrogen")
            if new_n < -_ROUND_OFF:
                return stop("state update would produce negative nitrogen; decrease step or check solver tolerance")
            correction = max(0.0, -new_n) * volume
            new_n = max(0.0, new_n)  # Only a bounded roundoff correction, recorded in the ledger.
            steps.append({"interval_index": interval_index, "start_h": t, "end_h": stop_time,
                          "step_h": dt, "dilution_h_inv": dilution, "nitrogen_feed_mmol_N_h": interval.nitrogen_rate,
                          "growth_rate_h_inv": mu, "nitrogen_net_uptake_mmol_N_g_model_h": qn,
                          "uptake_caps_mmol_g_model_h": caps, "solver_status": solution["status"],
                          "solver_residuals": deepcopy(solution.get("residuals", {}))})
            ledger["continuous_feed_mmol_N"] += feed_n
            ledger["net_cellular_removal_mmol_N"] += cellular_n
            ledger["dilution_removal_mmol_N"] += dilution_n
            ledger["roundoff_adjustment_mmol_N"] += correction
            t, x, n = stop_time, new_x, new_n
            record_state("step_end")
            apply_events()
    result["observation_comparisons"] = _compare(data.observations, states)
    return result
