"""Read-only reaction audit. Database annotations are candidates, not verification.

Uses exact rational arithmetic over the decimal numbers encoded in a COBRA JSON
model. Outputs every reaction, including exchange and biomass bookkeeping.
No reaction, formula, charge, bound or objective is changed.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import platform
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ELEMENTS = set("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split())
TOKEN = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d+)?|\.\d+)?")


def number(value):
    if value is None or isinstance(value, bool):
        raise ValueError("Missing or invalid numeric value")
    return Fraction(str(value))


def exact_text(value):
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    denominator = value.denominator
    for factor in (2, 5):
        while denominator % factor == 0:
            denominator //= factor
    if denominator == 1:
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    return str(value)


def parse_formula(formula):
    if not isinstance(formula, str) or not formula.strip():
        return {}, "MISSING_FORMULA", []
    formula = formula.strip()
    matches = list(TOKEN.finditer(formula))
    if "".join(m.group(0) for m in matches) != formula:
        return {}, "UNSUPPORTED_FORMULA", []
    atoms = defaultdict(Fraction)
    for match in matches:
        atoms[match.group(1)] += number(match.group(2) or 1)
    unknown = sorted(set(atoms) - ELEMENTS)
    return dict(atoms), "SYMBOLIC_FORMULA" if unknown else "DEFINED_FORMULA", unknown


def bound_direction(lower, upper):
    try:
        lower, upper = number(lower), number(upper)
    except (ValueError, ZeroDivisionError):
        return "INVALID_BOUNDS"
    if lower > upper:
        return "INVALID_BOUNDS"
    if lower == upper == 0:
        return "DISABLED"
    if lower < 0 < upper:
        return "REVERSIBLE"
    if lower >= 0 and upper > 0:
        return "FORWARD_ONLY"
    if lower < 0 and upper <= 0:
        return "REVERSE_ONLY"
    return "INVALID_BOUNDS"


def candidate_ids(annotation):
    result = []
    for namespace in ("biocyc", "metacyc", "metacyc.reaction", "metacyc.compound"):
        values = annotation.get(namespace, [])
        if isinstance(values, str):
            if values.lstrip().startswith("["):
                try:
                    values = ast.literal_eval(values)
                except (ValueError, SyntaxError):
                    values = [values]
            else:
                values = [values]
        if not isinstance(values, (list, tuple)):
            continue
        for value in values:
            value = str(value).strip()
            for prefix in ("META:", "metacyc:"):
                if value.startswith(prefix):
                    value = value[len(prefix):]
            if value and value not in result:
                result.append(value)
    return result


def role(reaction, metabolites):
    rid = reaction["id"]
    if rid.startswith("EX_"):
        return "EXCHANGE"
    if rid.startswith(("DM_", "SK_", "SINK_")):
        return "DEMAND_OR_SINK"
    if "biomass" in rid.lower():
        return "BIOMASS"
    coefficients = list(reaction["metabolites"].values())
    if not coefficients or not any(number(v) < 0 for v in coefficients) or not any(number(v) > 0 for v in coefficients):
        return "UNCLASSIFIED_ONE_SIDED"
    compartments = {metabolites[mid].get("compartment", "") for mid in reaction["metabolites"]}
    return "MULTICOMPARTMENT" if len(compartments) > 1 else "INTERNAL"


def evaluate(reaction, metabolites):
    elements = defaultdict(Fraction)
    charge = Fraction(0)
    missing_formula, symbolic, missing_charge = [], [], []
    lhs, rhs = [], []
    for mid, raw_coefficient in reaction["metabolites"].items():
        coefficient = number(raw_coefficient)
        if not coefficient:
            continue
        metabolite = metabolites[mid]
        atoms, formula_status, unknown = parse_formula(metabolite.get("formula"))
        if formula_status in ("MISSING_FORMULA", "UNSUPPORTED_FORMULA"):
            missing_formula.append(mid)
        if unknown:
            symbolic.append(mid)
        for atom, count in atoms.items():
            elements[atom] += coefficient * count
        try:
            charge += coefficient * number(metabolite.get("charge"))
        except (ValueError, ZeroDivisionError):
            missing_charge.append(mid)
        term = ("" if abs(coefficient) == 1 else exact_text(abs(coefficient)) + " ") + mid
        (lhs if coefficient < 0 else rhs).append(term)
    residual = {key: exact_text(value) for key, value in sorted(elements.items()) if value}
    atom_status = "INDETERMINATE" if missing_formula else "FAIL" if residual else "SYMBOLIC_BALANCED" if symbolic else "PASS"
    charge_status = "INDETERMINATE" if missing_charge else "FAIL" if charge else "PASS"
    reaction_role = role(reaction, metabolites)
    candidates = candidate_ids(reaction.get("annotation", {}))
    return {
        "reaction_id": reaction["id"], "name": reaction.get("name", ""),
        "role": reaction_role, "equation_forward": " + ".join(lhs) + " --> " + " + ".join(rhs),
        "lower_bound": exact_text(number(reaction["lower_bound"])),
        "upper_bound": exact_text(number(reaction["upper_bound"])),
        "bounds_direction": bound_direction(reaction["lower_bound"], reaction["upper_bound"]),
        "fixed_nonzero_flux": number(reaction["lower_bound"]) == number(reaction["upper_bound"]) != 0,
        "element_status": atom_status, "element_residual_products_minus_reactants": residual,
        "charge_status": charge_status, "charge_residual_products_minus_reactants": exact_text(charge),
        "missing_or_unsupported_formula": missing_formula, "symbolic_formula_metabolites": symbolic,
        "missing_charge": missing_charge, "metacyc_candidate_ids": candidates,
        "metacyc_equation_status": "NOT_VERIFIED_REFERENCE_NOT_LOADED",
        "metacyc_direction_status": "NOT_VERIFIED_REFERENCE_NOT_LOADED",
        "gene_reaction_rule": reaction.get("gene_reaction_rule", ""),
        "compartments": sorted({metabolites[mid].get("compartment", "") for mid in reaction["metabolites"]}),
        "bookkeeping_exception": reaction_role in ("EXCHANGE", "DEMAND_OR_SINK", "BIOMASS"),
    }


def write_csv(path, records):
    if not records:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        for record in records:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in record.items()})


def self_test():
    assert parse_formula("C2H4O2")[0] == {"C": 2, "H": 4, "O": 2}
    assert parse_formula("C2H3R")[1] == "SYMBOLIC_FORMULA"
    assert parse_formula(None)[1] == "MISSING_FORMULA"
    assert parse_formula("Fe(OH)3")[1] == "UNSUPPORTED_FORMULA"
    assert number("0.1") + number("0.2") == number("0.3")
    assert [bound_direction(*x) for x in [(0, 0), (-1, 1), (0, 1), (-1, 0), (1, 1), (1, -1)]] == ["DISABLED", "REVERSIBLE", "FORWARD_ONLY", "REVERSE_ONLY", "FORWARD_ONLY", "INVALID_BOUNDS"]
    metabolites = {"h2": {"formula": "H2", "charge": 0}, "o2": {"formula": "O2", "charge": 0}, "water": {"formula": "H2O", "charge": 0}}
    reaction = {"id": "test", "metabolites": {"h2": -1, "o2": "-0.5", "water": 1}, "lower_bound": 0, "upper_bound": 1000}
    result = evaluate(reaction, metabolites)
    assert result["element_status"] == result["charge_status"] == "PASS"
    metabolites["water"]["charge"] = 1
    assert evaluate(reaction, metabolites)["charge_status"] == "FAIL"
    metabolites["water"]["formula"] = None
    assert evaluate(reaction, metabolites)["element_status"] == "INDETERMINATE"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/generated/reaction-audit"))
    parser.add_argument("--include-source", action="store_true", help="Copy source model into the private audit output")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.model is None:
        if args.self_test:
            print("Exact arithmetic and direction unit checks passed")
            return 0
        parser.error("--model is required unless only --self-test is requested")
    raw = args.model.read_bytes()
    model = json.loads(raw, parse_float=Decimal)
    metabolites = {metabolite["id"]: metabolite for metabolite in model["metabolites"]}
    if len(metabolites) != len(model["metabolites"]):
        raise ValueError("Duplicate metabolite IDs")
    reactions = model["reactions"]
    if len({reaction["id"] for reaction in reactions}) != len(reactions):
        raise ValueError("Duplicate reaction IDs")
    rows = [evaluate(reaction, metabolites) for reaction in reactions]
    internal = [row for row in rows if not row["bookkeeping_exception"]]
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    summary = {
        "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(), "repository_commit": commit,
        "source_model_file": str(args.model), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_git_blob_sha1": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
        "python": platform.python_version(), "arithmetic": "Exact fractions from encoded decimal values; no tolerance", "model_changed": False,
        "total_reactions": len(rows), "metabolites": len(metabolites), "genes": len(model.get("genes", [])),
        "roles": dict(Counter(row["role"] for row in rows)), "directions_all": dict(Counter(row["bounds_direction"] for row in rows)),
        "non_bookkeeping_reactions": len(internal),
        "element_status_non_bookkeeping": dict(Counter(row["element_status"] for row in internal)),
        "charge_status_non_bookkeeping": dict(Counter(row["charge_status"] for row in internal)),
        "exact_element_failures_non_bookkeeping": [row["reaction_id"] for row in internal if row["element_status"] == "FAIL"],
        "exact_charge_failures_non_bookkeeping": [row["reaction_id"] for row in internal if row["charge_status"] == "FAIL"],
        "reactions_with_metacyc_candidates": sum(bool(row["metacyc_candidate_ids"]) for row in rows),
        "metacyc_comparison": "NOT_EXECUTED: versioned reference data not loaded; annotations do not establish correctness",
        "biological_direction_verification": "NOT_EXECUTED: bounds are classified, not accepted as chemical evidence",
        "limitations": ["Compound formulas/charges have not been authenticated against MetaCyc", "Generic formulas are not concrete chemical structures", "Exchange, sink and biomass residuals are retained but separated", "No thermodynamic or flux-cycle validation is implied"],
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (args.output / "all-reactions.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    write_csv(args.output / "all-reactions.csv", rows)
    write_csv(args.output / "non-bookkeeping-findings.csv", [row for row in internal if row["element_status"] != "PASS" or row["charge_status"] != "PASS"])
    metabolite_rows = [{"metabolite_id": item["id"], "name": item.get("name", ""), "compartment": item.get("compartment", ""), "formula": item.get("formula"), "charge": str(item.get("charge")), "formula_status": parse_formula(item.get("formula"))[1], "metacyc_candidate_ids": candidate_ids(item.get("annotation", {})), "metacyc_status": "NOT_VERIFIED_REFERENCE_NOT_LOADED"} for item in model["metabolites"]]
    write_csv(args.output / "all-metabolites.csv", metabolite_rows)
    if args.include_source:
        shutil.copyfile(args.model, args.output / "source-model.json")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
