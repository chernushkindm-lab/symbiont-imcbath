"""Compare preserved model encodings and rerun the numerical reference.

Run MEMOTE separately with scripts/run_memote.py --output reports/m10-audit.
This audit deliberately does not mutate model files or normalization.
"""
from __future__ import annotations
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cobra
from cobra.util.solver import linear_reaction_coefficients
from ruamel.yaml import YAML
from m10.metabocore.gem import MODEL_HASHES, reference_regression
from symbiont_imcbath.core import software_versions


def same_number(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-12)


def compare(a, b):
    diffs = []
    for collection in ("reactions", "metabolites", "genes"):
        aa, bb = getattr(a, collection), getattr(b, collection)
        if {x.id for x in aa} != {x.id for x in bb}:
            diffs.append({"field": collection, "reason": "identifier sets differ",
                          "only_in_json": sorted({x.id for x in aa} - {x.id for x in bb}),
                          "only_in_other": sorted({x.id for x in bb} - {x.id for x in aa})})
    for m in a.metabolites:
        if m.id not in b.metabolites:
            continue
        n = b.metabolites.get_by_id(m.id)
        for key in ("formula", "charge", "compartment"):
            if getattr(m, key) != getattr(n, key):
                diffs.append({"id": m.id, "field": key, "left": getattr(m, key), "right": getattr(n, key)})
    for r in a.reactions:
        if r.id not in b.reactions:
            continue
        s = b.reactions.get_by_id(r.id)
        for key in ("lower_bound", "upper_bound", "objective_coefficient"):
            if not same_number(getattr(r, key), getattr(s, key)):
                diffs.append({"id": r.id, "field": key, "left": getattr(r, key), "right": getattr(s, key)})
        if r.gene_reaction_rule != s.gene_reaction_rule and r.gpr != s.gpr:
            diffs.append({"id": r.id, "field": "gene_reaction_rule", "left": r.gene_reaction_rule, "right": s.gene_reaction_rule})
        rs, ss = {m.id: c for m, c in r.metabolites.items()}, {m.id: c for m, c in s.metabolites.items()}
        if set(rs) != set(ss) or any(not same_number(c, ss.get(k, float("inf"))) for k, c in rs.items()):
            diffs.append({"id": r.id, "field": "stoichiometry"})
    if a.objective.direction != b.objective.direction:
        diffs.append({"field": "objective.direction"})
    return diffs


def main():
    output = ROOT / "reports/m10-audit"
    output.mkdir(parents=True, exist_ok=True)
    paths = list(MODEL_HASHES)
    loaders = [cobra.io.load_json_model, cobra.io.read_sbml_model, cobra.io.load_yaml_model]
    models = {path: loader(ROOT / path) for path, loader in zip(paths, loaders)}
    hashes = {path: {"sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), "expected": MODEL_HASHES[path]} for path in paths}
    integrity = all(v["sha256"] == v["expected"] for v in hashes.values())
    base = models[paths[0]]
    comparisons = {path: compare(base, models[path]) for path in paths[1:]}
    mapping = YAML(typ="safe").load((ROOT / "configs/reaction_map.yaml").read_text(encoding="utf-8-sig"))
    mapped = []
    for role, spec in mapping["reactions"].items():
        reaction = base.reactions.get_by_id(spec["id"])
        valid = all(same_number(a, b) for a, b in zip(reaction.bounds, spec["default_bounds"]))
        if "metabolite" in spec:
            valid = valid and {m.id: c for m, c in reaction.metabolites.items()} == {spec["metabolite"]: spec["coefficient"]}
        if "objective_coefficient" in spec:
            valid = valid and same_number(reaction.objective_coefficient, spec["objective_coefficient"])
        mapped.append({"role": role, "id": reaction.id, "verified": valid, "bounds": list(reaction.bounds),
                       "stoichiometry": {m.id: c for m, c in reaction.metabolites.items()}})
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "hash_integrity": integrity,
              "artifact_hashes": hashes, "software_versions": software_versions(),
              "counts": {"reactions": len(base.reactions), "metabolites": len(base.metabolites), "genes": len(base.genes)},
              "comparison_scope": "IDs, reaction bounds, stoichiometry, GPR, metabolite formula/charge/compartment, objective; annotations intentionally separate",
              "numeric_comparison_tolerance": {"relative": 1e-12, "absolute": 1e-12},
              "differences_from_json": comparisons, "functional_consistency": not any(comparisons.values()),
              "runtime_audit_pair_consistent": not comparisons["ModelFiles/xml/iMcBath.xml"],
              "artifact_counts": {p: {"reactions": len(m.reactions), "metabolites": len(m.metabolites), "genes": len(m.genes)} for p, m in models.items()},
              "reaction_map": mapped,
              "objective": {r.id: c for r, c in linear_reaction_coefficients(base).items()}}
    (output / "model-integrity.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    reference = reference_regression()
    (output / "reference-regression.json").write_text(json.dumps(reference, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"hash_integrity": integrity, "functional_consistency": report["functional_consistency"],
                      "differences": {p: len(d) for p, d in comparisons.items()}, "reaction_map_valid": all(r["verified"] for r in mapped),
                      "reference_passed": reference["regression_passed"], "growth_rate_h": reference["growth_rate_h"]}))
    return 0 if integrity and report["functional_consistency"] and all(r["verified"] for r in mapped) and reference["regression_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
