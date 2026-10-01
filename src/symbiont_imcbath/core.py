"""Versioned iMcBath model loading, explicit edits and steady-state simulation.

Fluxes retain the published model's biomass normalization. Numerical feasibility
is not experimental validation, and a solver run is not a MEMOTE assessment.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from importlib import resources
from importlib.metadata import version
from pathlib import Path
import platform
from typing import Any, Mapping
import warnings

import cobra
import swiglpk
from cobra.flux_analysis import pfba
from cobra.util.solver import linear_reaction_coefficients

BASELINE_SHA256 = "92ae700bd42fae2339a1b2ad2d3d6c6011e7004d163bf4c708f4bed0b944bdda"
UPSTREAM_COMMIT = "f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160"
UPSTREAM_URL = "https://github.com/ChristianLieven/memote-m-capsulatus"
BIOMASS_ID = "BIOMASS_Mcapsulatus"
BASELINE_COUNTS = {"reactions": 913, "metabolites": 879, "genes": 730}
GLPK_FEASIBILITY_TOLERANCE = 1e-9
_PROFILE_KEYS = {
    "schema_version", "id", "description", "provenance", "assumptions",
    "reaction_bounds", "stoichiometry", "objective",
}


class ProfileError(ValueError):
    """An explicit model profile is malformed or names an unknown identifier."""


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def baseline_path() -> Path:
    """Locate packaged model data, with a source-checkout fallback."""
    bundled = Path(str(resources.files("symbiont_imcbath").joinpath("data/iMcBath.json")))
    return bundled if bundled.is_file() else _root() / "ModelFiles/json/iMcBath.json"


def software_versions() -> dict:
    return {"python": platform.python_version(), "cobra": cobra.__version__,
            "optlang": version("optlang"), "swiglpk": version("swiglpk"),
            "glpk": swiglpk.glp_version()}


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ProfileError(f"{label} must be a finite number (not a boolean)")
    try:
        number = float(value)
    except OverflowError as error:
        raise ProfileError(f"{label} must be finite") from error
    if not math.isfinite(number):
        raise ProfileError(f"{label} must be finite")
    return number


def _mapping(value: Any, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ProfileError(f"{label} must be an object")
    return value


def _keys(value: Mapping, allowed: set[str], label: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ProfileError(f"Unknown {label} field(s): {', '.join(sorted(map(str, unknown)))}")


def _identifier(value: Any, collection: Any, label: str) -> Any:
    if not isinstance(value, str) or value not in collection:
        raise ProfileError(f"Unknown {label}: {value!r}")
    return collection.get_by_id(value)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _json_float(value: str) -> float:
    return _finite(float(value), "JSON number")


def _reject_json_constant(value: str) -> None:
    raise ProfileError(f"JSON number must be finite: {value}")


def read_json_document(path: str | Path) -> Any:
    """Read strict JSON, rejecting duplicate keys and nonfinite numbers."""
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_no_duplicate_keys,
                         parse_float=_json_float, parse_constant=_reject_json_constant)


def load_profile(source: str | Path | Mapping) -> dict:
    """Read a JSON profile or copy a mapping. Built-in names omit ``.json``."""
    if isinstance(source, Mapping):
        profile = copy.deepcopy(dict(source))
    else:
        path = Path(source)
        if not path.is_file() and str(source) in {"upstream-baseline", "symbiont-reference"}:
            name = f"{source}.json"
            bundled = Path(str(resources.files("symbiont_imcbath").joinpath("data/profiles", name)))
            path = bundled if bundled.is_file() else _root() / "profiles" / name
        profile = read_json_document(path)
    _mapping(profile, "profile")
    _keys(profile, _PROFILE_KEYS, "profile")
    if type(profile.get("schema_version")) is not int or profile["schema_version"] != 1:
        raise ProfileError("schema_version must be 1")
    if not isinstance(profile.get("id"), str) or not profile["id"].strip():
        raise ProfileError("profile id must be a nonempty string")
    if "description" in profile and not isinstance(profile["description"], str):
        raise ProfileError("description must be a string")
    provenance = _mapping(profile.get("provenance"), "provenance")
    _keys(provenance, {"source", "status", "notes"}, "provenance")
    for name in ("source", "status"):
        if not isinstance(provenance.get(name), str) or not provenance[name].strip():
            raise ProfileError(f"provenance.{name} must be a nonempty string")
    if "notes" in provenance and not isinstance(provenance["notes"], str):
        raise ProfileError("provenance.notes must be a string")
    assumptions = profile.get("assumptions", [])
    if not isinstance(assumptions, list) or any(not isinstance(item, str) for item in assumptions):
        raise ProfileError("assumptions must be an array of strings")
    return profile


def load_baseline(model_path: str | Path | None = None) -> cobra.Model:
    """Load a fresh GLPK model only when its exact bytes match pinned upstream.

    This function never writes the source. Every caller receives a separate
    model; edits must be explicit profiles or in-memory COBRApy operations.
    """
    path = Path(model_path) if model_path is not None else baseline_path()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != BASELINE_SHA256:
        raise ValueError(f"Baseline SHA256 mismatch: expected {BASELINE_SHA256}, got {digest}")
    model = cobra.io.load_json_model(str(path))
    model.solver = "glpk"
    model.solver.configuration.tolerances.feasibility = GLPK_FEASIBILITY_TOLERANCE
    model._symbiont_provenance = {  # Runtime metadata; exported in a separate manifest.
        "baseline_sha256": digest,
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_url": UPSTREAM_URL,
        "baseline_path": str(path.resolve()),
        "profiles": [],
        "assumptions": [
            "Published iMcBath biomass units are retained without renormalization.",
            "Steady-state maximum capacity is not a validated process growth forecast.",
        ],
    }
    return model


def model_info(model: cobra.Model) -> dict:
    coefficients = linear_reaction_coefficients(model)
    return {
        "id": model.id,
        "counts": {"reactions": len(model.reactions), "metabolites": len(model.metabolites), "genes": len(model.genes)},
        "solver": "glpk" if "glpk" in model.solver.interface.__name__ else model.solver.interface.__name__,
        "software_versions": software_versions(),
        "objective": {"direction": model.objective.direction, "coefficients": {r.id: float(c) for r, c in coefficients.items()}},
        "provenance": copy.deepcopy(getattr(model, "_symbiont_provenance", {"status": "untracked_model"})),
    }


def inspect_reaction(model: cobra.Model, reaction_id: str) -> dict:
    reaction = _identifier(reaction_id, model.reactions, "reaction")
    return {
        "id": reaction.id, "name": reaction.name, "equation": reaction.reaction,
        "lower_bound": reaction.lower_bound, "upper_bound": reaction.upper_bound,
        "objective_coefficient": float(reaction.objective_coefficient),
        "gene_reaction_rule": reaction.gene_reaction_rule,
        "metabolites": {met.id: float(coefficient) for met, coefficient in sorted(reaction.metabolites.items(), key=lambda item: item[0].id)},
    }


def apply_profile(model: cobra.Model, source: str | Path | Mapping) -> tuple[cobra.Model, dict]:
    """Apply validated absolute replacements to a copy and return its audit trail.

    A stoichiometric value replaces the coefficient for that metabolite. Zero
    removes it. Other metabolites remain unchanged; no value is a delta.
    """
    profile = load_profile(source)
    bounds = _mapping(profile.get("reaction_bounds", {}), "reaction_bounds")
    stoichiometry = _mapping(profile.get("stoichiometry", {}), "stoichiometry")
    planned_bounds = []
    planned_stoichiometry = []
    for reaction_id, change in bounds.items():
        reaction = _identifier(reaction_id, model.reactions, "reaction")
        change = _mapping(change, f"reaction_bounds.{reaction_id}")
        _keys(change, {"lower_bound", "upper_bound"}, f"bounds for {reaction_id}")
        if not change:
            raise ProfileError(f"Bounds for {reaction_id} cannot be empty")
        lower = _finite(change.get("lower_bound", reaction.lower_bound), f"{reaction_id}.lower_bound")
        upper = _finite(change.get("upper_bound", reaction.upper_bound), f"{reaction_id}.upper_bound")
        if lower > upper:
            raise ProfileError(f"Inverted bounds for {reaction_id}: {lower} > {upper}")
        planned_bounds.append((reaction_id, lower, upper))
    for reaction_id, coefficients in stoichiometry.items():
        _identifier(reaction_id, model.reactions, "reaction")
        coefficients = _mapping(coefficients, f"stoichiometry.{reaction_id}")
        if not coefficients:
            raise ProfileError(f"Stoichiometry for {reaction_id} cannot be empty")
        for metabolite_id, coefficient in coefficients.items():
            _identifier(metabolite_id, model.metabolites, "metabolite")
            planned_stoichiometry.append((reaction_id, metabolite_id, _finite(coefficient, f"{reaction_id}.{metabolite_id}")))
    objective = None
    if "objective" in profile:
        objective = _mapping(profile["objective"], "objective")
        _keys(objective, {"direction", "coefficients"}, "objective")
        if objective.get("direction") not in {"max", "min"}:
            raise ProfileError("objective.direction must be max or min")
        coefficients = _mapping(objective.get("coefficients"), "objective.coefficients")
        if not coefficients:
            raise ProfileError("objective.coefficients cannot be empty")
        for reaction_id, coefficient in coefficients.items():
            _identifier(reaction_id, model.reactions, "reaction")
            _finite(coefficient, f"objective.{reaction_id}")
        if not any(coefficients.values()):
            raise ProfileError("objective must contain a nonzero coefficient")
    # Validation is complete before any model is changed.
    patched = model.copy()
    audit = []
    for reaction_id, lower, upper in planned_bounds:
        reaction = patched.reactions.get_by_id(reaction_id)
        before = {"lower_bound": reaction.lower_bound, "upper_bound": reaction.upper_bound}
        reaction.bounds = (lower, upper)
        audit.append({"kind": "reaction_bounds", "reaction_id": reaction_id, "before": before,
                      "after": {"lower_bound": lower, "upper_bound": upper}})
    for reaction_id, metabolite_id, coefficient in planned_stoichiometry:
        reaction = patched.reactions.get_by_id(reaction_id)
        metabolite = patched.metabolites.get_by_id(metabolite_id)
        before = float(reaction.metabolites.get(metabolite, 0.0))
        reaction.add_metabolites({metabolite: coefficient}, combine=False)
        audit.append({"kind": "absolute_stoichiometry", "reaction_id": reaction_id,
                      "metabolite_id": metabolite_id, "before": before, "after": coefficient})
    if objective is not None:
        before = model_info(patched)["objective"]
        patched.objective = {patched.reactions.get_by_id(r): float(c) for r, c in objective["coefficients"].items()}
        patched.objective.direction = objective["direction"]
        audit.append({"kind": "objective", "before": before, "after": model_info(patched)["objective"]})
    record = {
        "id": profile["id"],
        "profile_sha256": hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
        "provenance": copy.deepcopy(profile["provenance"]),
        "assumptions": list(profile.get("assumptions", [])),
        "changes": audit,
    }
    history = copy.deepcopy(getattr(model, "_symbiont_provenance", {"status": "untracked_model", "profiles": [], "assumptions": []}))
    history.setdefault("profiles", []).append(record)
    history.setdefault("assumptions", []).extend(record["assumptions"])
    patched._symbiont_provenance = history
    return patched, copy.deepcopy(history)


def solve(model: cobra.Model, method: str = "pfba", uptake_caps: Mapping[str, float] | None = None) -> dict:
    """Solve FBA/pFBA and report biomass flux, feasibility and temporary caps.

    Positive uptake caps use the conventional negative exchange-flux direction.
    Reported uptake rates are metabolite amounts (coefficient times flux), so
    rescaling an uncapped exchange does not silently rescale molecular uptake.
    The model and its bounds are restored after the call. Infeasible solutions
    return null predictions, never an invented zero growth measurement.
    """
    if method not in {"fba", "pfba"}:
        raise ProfileError("method must be fba or pfba")
    _identifier(BIOMASS_ID, model.reactions, "biomass reaction")
    caps = dict(_mapping(uptake_caps if uptake_caps is not None else {}, "uptake_caps"))
    exchange_reactions = list(model.exchanges)
    exchange_ids = {reaction.id for reaction in exchange_reactions}
    for reaction in exchange_reactions:
        if len(reaction.metabolites) != 1:
            raise ProfileError(f"Cannot summarize multi-metabolite exchange {reaction.id} as one uptake rate")
    for reaction_id, cap in caps.items():
        reaction = _identifier(reaction_id, model.reactions, "exchange reaction")
        number = _finite(cap, f"uptake_caps.{reaction_id}")
        if number < 0:
            raise ProfileError(f"Uptake cap for {reaction_id} must be nonnegative")
        if reaction_id not in exchange_ids or len(reaction.metabolites) != 1 or next(iter(reaction.metabolites.values())) != -1:
            raise ProfileError(f"{reaction_id} is not a conventional single-metabolite exchange with coefficient -1")
        if -number > reaction.upper_bound:
            raise ProfileError(f"Uptake cap for {reaction_id} would invert its bounds")
        caps[reaction_id] = number
    result = {
        "status": None, "method": method, "solver": "glpk", "growth_rate_h": None,
        "solver_feasibility_tolerance": GLPK_FEASIBILITY_TOLERANCE,
        "software_versions": software_versions(),
        "objective_value": None, "pfba_total_flux": None,
        "fluxes": {}, "uptake_rates": {},
        "residuals": {"max_mass_balance": None, "max_bound_violation": None},
        "numerically_feasible": False, "uptake_caps": caps,
        "units": {"growth_rate_h": "1/h in published model biomass units", "fluxes": "mmol reaction/(g modeled biomass h) except biomass pseudo-reaction",
                  "uptake_rates": "mmol exchanged metabolite/(g modeled biomass h)"},
        "provenance": copy.deepcopy(getattr(model, "_symbiont_provenance", {"status": "untracked_model"})),
        "assumptions": list(getattr(model, "_symbiont_provenance", {}).get("assumptions", [])),
    }
    with model:
        model.solver = "glpk"
        model.solver.configuration.tolerances.feasibility = GLPK_FEASIBILITY_TOLERANCE
        for reaction_id, cap in caps.items():
            model.reactions.get_by_id(reaction_id).lower_bound = -cap
        objective_coefficients = linear_reaction_coefficients(model)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            solution = model.optimize(raise_error=False)
        result["status"] = solution.status
        if solution.status != "optimal":
            result["message"] = "No optimal feasible flux vector; growth and uptake predictions are unavailable."
            return result
        if method == "pfba":
            try:
                solution = pfba(model, fraction_of_optimum=1.0)
            except cobra.exceptions.OptimizationError as error:
                result["status"] = "pfba_failed"
                result["message"] = str(error)
                return result
            result["pfba_total_flux"] = float(solution.objective_value)
        result["status"] = solution.status
        if solution.status != "optimal":
            result["message"] = "No optimal parsimonious solution; predictions are unavailable."
            return result
        fluxes = {str(key): float(value) for key, value in solution.fluxes.items()}
        if any(not math.isfinite(value) for value in fluxes.values()):
            result["status"] = "nonfinite_solution"
            result["message"] = "Solver returned nonfinite fluxes; predictions are unavailable."
            return result
        mass = {met.id: 0.0 for met in model.metabolites}
        bound_violation = 0.0
        for reaction in model.reactions:
            flux = fluxes[reaction.id]
            bound_violation = max(bound_violation, reaction.lower_bound - flux, flux - reaction.upper_bound)
            for metabolite, coefficient in reaction.metabolites.items():
                mass[metabolite.id] += coefficient * flux
        result.update({
            "growth_rate_h": fluxes[BIOMASS_ID],
            "objective_value": sum(float(coefficient) * fluxes[reaction.id] for reaction, coefficient in objective_coefficients.items()),
            "fluxes": fluxes,
            "uptake_rates": {reaction.id: max(0.0, float(next(iter(reaction.metabolites.values()))) * fluxes[reaction.id])
                             for reaction in exchange_reactions},
            "residuals": {"max_mass_balance": max(map(abs, mass.values()), default=0.0), "max_bound_violation": max(0.0, bound_violation)},
        })
        result["numerically_feasible"] = max(result["residuals"].values()) <= 1e-7
    return result


def protected_baseline_paths(model: cobra.Model) -> set[Path]:
    """Paths that must never be replaced by an export or a CLI response."""
    protected = {baseline_path().resolve()}
    for extension, folder in (("json", "json"), ("xml", "xml"), ("yml", "yml")):
        protected.add((_root() / "ModelFiles" / folder / f"iMcBath.{extension}").resolve())
        protected.add((Path(str(resources.files("symbiont_imcbath"))) / "data" / f"iMcBath.{extension}").resolve())
    source_path = getattr(model, "_symbiont_provenance", {}).get("baseline_path")
    if source_path:
        protected.add(Path(source_path).resolve())
    return protected


def export_model(model: cobra.Model, destination: str | Path, format: str | None = None, overwrite: bool = False) -> dict:
    """Export an edited copy and an audit manifest, protecting baseline files."""
    path = Path(destination).resolve()
    selected_format = format or ("sbml" if path.suffix.lower() in {".xml", ".sbml"} else "json")
    if selected_format not in {"json", "sbml"}:
        raise ProfileError("format must be json or sbml")
    manifest = path.with_name(path.name + ".provenance.json").resolve()
    if path == manifest:
        raise ValueError("Export model and provenance manifest must use separate paths")
    if {path, manifest} & protected_baseline_paths(model):
        raise ValueError("Cannot overwrite an immutable upstream baseline file")
    if not overwrite and (path.exists() or manifest.exists()):
        raise FileExistsError(f"Export or manifest already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if selected_format == "json":
        cobra.io.save_json_model(model, str(path), pretty=True)
    else:
        cobra.io.write_sbml_model(model, str(path))
    metadata = model_info(model)
    metadata.update({"export_format": selected_format, "export_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest.write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"model_path": str(path), "manifest_path": str(manifest), **metadata}
