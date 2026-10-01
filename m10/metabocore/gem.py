"""Evidence-gated M10 calls into the immutable, tested iMcBath adapter.

Positive uptake intervals map to negative exchange bounds. This module does not
infer flux from concentration, identify producer biomass, or fit process data.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping
import xml.etree.ElementTree as ET

SURROGATE_NOTICE = "Bath GEM used as a conditional surrogate for VS1; equivalence is not experimentally established."
FLUX_UNIT = "mmol/(g_model_biomass h)"
REQUIRED_UPTAKES = {"EX_ch4_e", "EX_o2_e", "EX_nh4_e"}
OPTIONAL_UPTAKES = {"EX_pi_e", "EX_cu2_e", "EX_fe2_e"}
ROOT = Path(__file__).resolve().parents[2]
MODEL_HASHES = {
    "ModelFiles/json/iMcBath.json": "92ae700bd42fae2339a1b2ad2d3d6c6011e7004d163bf4c708f4bed0b944bdda",
    "ModelFiles/xml/iMcBath.xml": "c2591237d8968164faeb8fafe741a9a42f95131b919086d5eb1a14b159fee092",
    "ModelFiles/yml/iMcBath.yml": "ade8aa1a71d1fb406f7ab85aab40b51477876720eff0a4558d0eb0e777836038",
}


def _number(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} must be finite") from error
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{label} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value


def _object(value: Any, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def model_audit_summary() -> dict:
    """Read local audit evidence; never call an archived report a fresh pass."""
    hashes = {name: {"expected": expected, "actual": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()}
              for name, expected in MODEL_HASHES.items()}
    immutable = all(v["actual"] == v["expected"] for v in hashes.values())
    current = ROOT / "reports/m10-audit"
    inherited = ROOT / "reports/baseline-audit"
    audit = current if (current / "run-metadata.json").is_file() else inherited
    metadata = json.loads((audit / "run-metadata.json").read_text(encoding="utf-8")) if (audit / "run-metadata.json").is_file() else {}
    cases = []
    if (audit / "junit.xml").is_file():
        cases = list(ET.parse(audit / "junit.xml").getroot().iter("testcase"))
    counts = {"tests": len(cases), "failed": sum(c.find("failure") is not None for c in cases),
              "errors": sum(c.find("error") is not None for c in cases),
              "skipped": sum(c.find("skipped") is not None for c in cases)}
    counts["passed"] = counts["tests"] - counts["failed"] - counts["errors"] - counts["skipped"]
    audit_matches = metadata.get("model_sha256") == MODEL_HASHES["ModelFiles/xml/iMcBath.xml"]
    reaction_map = ROOT / "configs/reaction_map.yaml"
    scored_path = audit / "memote-scored.json"
    scored = json.loads(scored_path.read_text(encoding="utf-8")) if scored_path.is_file() else {}
    total_score = scored.get("score", {}).get("total_score")
    comparison_path = current / "model-integrity.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8")) if comparison_path.is_file() else {}
    return {
        "status": "conditional" if immutable else "blocked", "model_integrity": "verified" if immutable else "hash_mismatch",
        "audit_model_matches_runtime_artifact": audit_matches,
        "runtime_audit_pair_consistent": comparison.get("runtime_audit_pair_consistent"),
        "all_encodings_functionally_identical": comparison.get("functional_consistency"),
        "encoding_differences": comparison.get("differences_from_json", {}),
        "reaction_map_sha256": hashlib.sha256(reaction_map.read_bytes()).hexdigest() if reaction_map.is_file() else None,
        "artifact_hashes": hashes, "structural_audit_status": metadata.get("status", "not_executed"),
        "audit_evidence": "fresh_m10_run" if audit == current else "inherited_repository_run",
        "audit_path": str(audit.relative_to(ROOT)), "audit_started_utc": metadata.get("started_utc"),
        "audit_finished_utc": metadata.get("finished_utc"), "audit_exit_code": metadata.get("pytest_exit_code"),
        "audit_score_percent": None if total_score is None else 100 * total_score,
        "audit_counts": counts, "experimental_validation": "not_qualified", "forecast_qualification": "not_qualified",
        "surrogate_notice": SURROGATE_NOTICE,
        "limitations": ["Published biomass normalization is unresolved; no 1/0.902 correction is applied.",
                        "MEMOTE findings and score describe model quality, not predictive accuracy.",
                        "Total dry residue, community biomass and modeled producer biomass are distinct observables."],
    }


def reference_regression() -> dict:
    """Pure software regression; never labeled a historical fit or validation."""
    from symbiont_imcbath.core import apply_profile, load_baseline, solve
    model, _ = apply_profile(load_baseline(), "symbiont-reference")
    result = solve(model, method="pfba")
    expected = 0.2255827702718434
    result.update({"mode": "model_regression", "provenance_class": "synthetic_assumption",
                   "expected_growth_rate_h": expected, "regression_absolute_tolerance_h": 1e-9,
                   "regression_passed": result["growth_rate_h"] is not None and abs(result["growth_rate_h"] - expected) <= 1e-9,
                   "surrogate_notice": SURROGATE_NOTICE})
    return result


def capacity(request: Mapping[str, Any]) -> dict:
    """Return conditional flux capacity or a transparent evidence/solver gate.

    ``uptake_bounds`` are positive cellular-uptake intervals, with exact units,
    provenance and source. Capacity mode allows assumed scenarios; reconciliation
    additionally requires measurement lineage and a declared validated biomass
    normalization/producer-attribution mapping. No online calibration is done.
    """
    from symbiont_imcbath.core import apply_profile, load_baseline, solve
    d = _object(request, "request")
    allowed = {"schema_version", "run_id", "window_id", "mode", "scenario_id", "uptake_bounds",
               "biomass", "biomass_mapping", "fva_reactions", "sensitivity_fraction"}
    if set(d) - allowed:
        raise ValueError(f"Unknown capacity fields: {sorted(set(d) - allowed)}")
    if type(d.get("schema_version")) is not int or d["schema_version"] != 1:
        raise ValueError("schema_version must be integer 1")
    run_id = _text(d.get("run_id"), "run_id")
    window_id = _text(d.get("window_id"), "window_id")
    mode = d.get("mode", "capacity")
    if mode not in {"capacity", "reconciliation"}:
        raise ValueError("mode must be capacity or reconciliation")
    if d.get("scenario_id", "symbiont-reference") != "symbiont-reference":
        raise ValueError("Only the versioned symbiont-reference scenario is supported")
    bounds = _object(d.get("uptake_bounds", {}), "uptake_bounds")
    if set(bounds) - REQUIRED_UPTAKES - OPTIONAL_UPTAKES:
        raise ValueError("Unsupported uptake reaction; use only the verified CH4/O2/NH4/P/Cu/Fe mapping")
    mapping = d.get("biomass_mapping")
    biomass = d.get("biomass")
    factor = biomass_value = None
    if mapping is not None:
        mapping = _object(mapping, "biomass_mapping")
        factor = _number(mapping.get("factor_g_model_per_g_residue"), "biomass_mapping.factor", positive=True)
        _text(mapping.get("source"), "biomass_mapping.source")
        if mapping.get("status") not in {"assumed", "validated"}:
            raise ValueError("biomass_mapping.status must be assumed or validated")
    if biomass is not None:
        biomass = _object(biomass, "biomass")
        if biomass.get("unit") != "g_dry_residue/L":
            raise ValueError("biomass.unit must be g_dry_residue/L; do not relabel dry residue as DCW")
        biomass_value = _number(biomass.get("value"), "biomass.value", positive=True)
        _text(biomass.get("source"), "biomass.source")
    if factor is not None and biomass_value is not None and not math.isfinite(factor * biomass_value):
        raise ValueError("Mapped biomass must be finite")
    provenance, changes, reasons = {}, {}, []
    for reaction_id, item in bounds.items():
        b = _object(item, f"uptake_bounds.{reaction_id}")
        if b.get("unit") != FLUX_UNIT:
            raise ValueError(f"{reaction_id}: unit must be {FLUX_UNIT}; concentration is not a flux")
        lo, hi = _number(b.get("lower"), reaction_id + ".lower"), _number(b.get("upper"), reaction_id + ".upper")
        if lo > hi:
            raise ValueError(f"{reaction_id}: inverted positive uptake interval")
        if b.get("provenance") not in {"measured", "recalculated", "assumed"}:
            raise ValueError(f"{reaction_id}: unsupported provenance class")
        _text(b.get("source"), reaction_id + ".source")
        parents = b.get("parent_observation_ids", [])
        if not isinstance(parents, list) or any(not isinstance(p, str) or not p for p in parents):
            raise ValueError(f"{reaction_id}: parent_observation_ids must be a list of IDs")
        if mode == "reconciliation" and (b["provenance"] == "assumed" or not parents):
            reasons.append(f"{reaction_id}: accepted cellular uptake evidence with parent observations is required")
        changes[reaction_id] = {"lower_bound": -hi, "upper_bound": -lo}
        provenance[reaction_id] = deepcopy(dict(b))
    missing = REQUIRED_UPTAKES - set(bounds)
    if missing:
        reasons.append("Missing explicit uptake constraints: " + ", ".join(sorted(missing)))
    if mode == "reconciliation" and (mapping is None or mapping.get("status") != "validated"):
        reasons.append("Measured reconciliation requires validated dry-residue/model-biomass and producer-attribution mapping")
    audit = model_audit_summary()
    if audit["model_integrity"] != "verified":
        reasons.append("Pinned model artifact hash mismatch")
    result = {"schema_version": 1, "run_id": run_id, "window_id": window_id, "mode": mode,
              "status": "blocked" if reasons else "conditional", "reasons": reasons,
              "solver_status": "not_run", "mu_capacity_h": None, "gross_capacity_g_model_L_h": None,
              "gross_capacity_status": "blocked_missing_biomass_mapping" if factor is None or biomass_value is None else "conditional",
              "uptake_provenance": provenance, "biomass_mapping": deepcopy(mapping),
              "biomass_observation": deepcopy(biomass), "surrogate_notice": SURROGATE_NOTICE,
              "model_audit": audit, "experimental_validation": "not_qualified", "forecast_qualification": "not_qualified",
              "assumptions": ["sMMO enabled; pMMO routes disabled by explicit scenario, not inferred from total Cu.",
                              "ATPM fixed at 8.39; other non-C/N nutrient supplies inherit permissive model bounds unless specified.",
                              "Gross capacity at supplied state is not observed formation, harvested productivity, or a trajectory forecast.",
                              "FVA feasible ranges are not statistical prediction intervals."],
              "created_utc": datetime.now(timezone.utc).isoformat()}
    if reasons:
        return result
    model, _ = apply_profile(load_baseline(), "symbiont-reference")
    # The inherited reference leaves CO import open; close it explicitly for
    # this methane-only scenario and retain that change in the profile audit.
    changes["EX_co_e"] = {"lower_bound": 0, "upper_bound": 1000}
    result["assumptions"].append("CO import is explicitly closed in the M10 overlay; the inherited reference leaves EX_co_e permissive.")
    profile = {"schema_version": 1, "id": f"m10:{run_id}:{window_id}",
               "provenance": {"source": "M10 capacity request; see uptake_provenance", "status": "conditional_scenario"},
               "reaction_bounds": changes, "assumptions": [SURROGATE_NOTICE]}
    model, history = apply_profile(model, profile)
    # Record every open C/N source and fail if the scenario contains an undeclared
    # substrate. This includes single-metabolite sinks, not only EX reactions.
    open_cn = []
    for reaction in model.boundary:
        for met, coefficient in reaction.metabolites.items():
            imports = (coefficient < 0 and reaction.lower_bound < 0) or (coefficient > 0 and reaction.upper_bound > 0)
            if imports and (met.elements.get("C", 0) or met.elements.get("N", 0)):
                open_cn.append({"reaction_id": reaction.id, "metabolite_id": met.id, "formula": met.formula,
                                "bounds": list(reaction.bounds)})
    result["open_carbon_nitrogen_sources"] = open_cn
    unexpected = {r["reaction_id"] for r in open_cn} - {"EX_ch4_e", "EX_nh4_e"}
    if unexpected:
        result.update(status="blocked", reasons=["Undeclared C/N source(s): " + ", ".join(sorted(unexpected))])
        return result
    model.solver.configuration.timeout = 10
    result["solver_timeout_seconds"] = 10
    solved = solve(model, method="pfba")
    result.update(solver_status=solved["status"], solver=solved,
                  profile_provenance=history,
                  active_exchange_bounds={r.id: list(r.bounds) for r in model.exchanges})
    result["request_sha256"] = hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if solved["status"] != "optimal" or not solved["numerically_feasible"]:
        result.update(status="blocked", reasons=["Solver did not return an optimal numerically feasible state"],
                      gross_capacity_status="blocked_solver")
        return result
    mu = solved["growth_rate_h"]
    result["mu_capacity_h"] = mu
    if factor is not None and biomass_value is not None:
        gross = mu * factor * biomass_value
        if not math.isfinite(gross):
            raise ValueError("Derived gross capacity is nonfinite")
        result["gross_capacity_g_model_L_h"] = gross
    result["binding_uptake_bounds"] = [r for r, b in bounds.items()
        if math.isclose(solved["uptake_rates"][r], b["upper"], abs_tol=1e-7, rel_tol=0)]
    targets = d.get("fva_reactions", [])
    if not isinstance(targets, list) or len(targets) > 8 or any(not isinstance(r, str) or r not in {"EX_ch4_e", "EX_o2_e", "EX_co2_e", "EX_nh4_e", "ATPM", "SMMOi", "PMMOipp", "PMMODCipp"} for r in targets):
        raise ValueError("fva_reactions must contain at most eight verified gas/N/MMO/ATPM IDs")
    if targets:
        from cobra.flux_analysis import flux_variability_analysis
        fva = flux_variability_analysis(model, reaction_list=targets, fraction_of_optimum=1.0, processes=1)
        result["fva"] = {"kind": "feasible_flux_range_at_optimum", "unit": FLUX_UNIT,
                         "statistical_interval": False, "reactions": fva.to_dict(orient="index")}
    fraction = d.get("sensitivity_fraction")
    if fraction is not None:
        fraction = _number(fraction, "sensitivity_fraction", positive=True)
        if fraction > 0.2:
            raise ValueError("sensitivity_fraction must be at most 0.2")
        sensitivities = {}
        for rid in sorted(REQUIRED_UPTAKES):
            cap = float(bounds[rid]["upper"])
            if cap == 0:
                continue
            perturbed = solve(model, method="fba", uptake_caps={rid: cap * (1 + fraction)})
            new_mu = perturbed["growth_rate_h"] if perturbed["numerically_feasible"] else None
            sensitivities[rid] = {"cap_change": cap * fraction, "mu_change_h": None if new_mu is None else new_mu - mu,
                                  "dmu_dcap": None if new_mu is None else (new_mu - mu) / (cap * fraction),
                                  "solver_status": perturbed["status"]}
        result["finite_perturbation_sensitivity"] = {"fraction": fraction, "interpretation": "model dependence; not a causal diagnosis", "reactions": sensitivities}
    return result
