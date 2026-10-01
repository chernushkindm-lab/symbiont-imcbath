# Editing coefficients reproducibly

Create a JSON profile for each reviewed scenario. Keep the upstream ModelFiles/
and bundled src/symbiont_imcbath/data/iMcBath.* unchanged. The loader verifies
their provenance. Run `python -m symbiont_imcbath inspect REACTION_ID` to list
actual bounds, metabolite IDs and coefficients. Repeated `--profile` options
apply in order; later entries replace earlier values for the same fields.

| Field | Meaning |
| --- | --- |
| schema_version | Integer 1 |
| id | Nonempty scenario/version identifier |
| provenance | Required source and status strings; optional notes |
| assumptions | List of declared assumptions |
| reaction_bounds | Reaction ID mapped to lower_bound and/or upper_bound |
| stoichiometry | Reaction ID mapped to metabolite IDs and absolute coefficients |
| objective | direction (max/min), coefficients mapping reaction IDs to weights |

Unknown fields/IDs, duplicate JSON keys, nonfinite values, inverted bounds and
empty objectives are rejected. Missing bound sides or stoichiometric entries
retain their previous values. Zero removes a metabolite from that reaction.
Nonzero entries may add an existing model metabolite. The API does not invent
new metabolite definitions. Syntactic validity does not establish biological
correctness.

This Python pattern shows an absolute stoichiometric replacement, avoiding
COBRApy's default additive semantics:

```python
from symbiont_imcbath.core import load_baseline, inspect_reaction, apply_profile

model = load_baseline()
reaction_id = "ATPM"
current = inspect_reaction(model, reaction_id)
coefficient = current["metabolites"]["atp_c"]
profile = {
    "schema_version": 1,
    "id": "reviewed-stoichiometry-example",
    "provenance": {"source": "Replace with a traceable scientific basis", "status": "proposed"},
    "stoichiometry": {reaction_id: {"atp_c": coefficient}},
}
# This example writes the same value. Choose a justified replacement and all
# chemically coupled changes before using a changed model.
edited, audit = apply_profile(model, profile)
```

Maintenance bounds, biomass composition, electron-transfer stoichiometry and
process conversion assumptions have different meanings. A gas-availability
factor cannot repair chemical imbalance. Change both ATPM bounds when assuming
a fixed flux; changing only one side alters its interpretation or may invert
the bounds.

`solve(..., uptake_caps={...})` takes positive capacities and temporarily sets
conventional exchange lower bounds to their negative values. It replaces those
bounds, so it can relax an earlier profile constraint; it restores them afterward.
If combining physical availability with a separate physiological ceiling,
calculate their minimum explicitly before calling. This helper accepts only
single-metabolite exchanges with coefficient -1. Direct profile bounds support
other forms. Raw exchange reaction flux and molecular uptake are distinct when
an exchange coefficient is changed.

Exports contain model JSON or SBML plus a provenance manifest. Audit edited SBML
with `python scripts/run_memote.py --model reports/generated/edited-model.xml`
and compare against the pinned baseline. Numerical residuals establish whether
a solution satisfies encoded equations; they do not establish that the chemistry,
biomass normalization or strain equivalence is correct.
