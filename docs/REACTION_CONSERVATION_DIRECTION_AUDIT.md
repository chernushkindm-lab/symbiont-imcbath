# Reaction conservation and direction audit — 3 October 2026

**Status: encoded-model audit completed; MetaCyc reference reconciliation NOT completed.**

## Provenance

Baseline main commit: `417fa2bb331eec7a2b49350eb10b3604369b55fd`.
Model: `ModelFiles/json/iMcBath.json`.
JSON SHA-256: `92ae700bd42fae2339a1b2ad2d3d6c6011e7004d163bf4c708f4bed0b944bdda`.
JSON Git blob SHA-1: `f33b986e4b33dc26184dddeb9815b88630f2338b`.
Executed audit-code commit: `f9f6c7f8d1aa09c98fdd26ae7731ad5f79dd9aa1`.
[GitHub Actions run 37111859503](https://github.com/chernushkindm-lab/symbiont-imcbath/actions/runs/37111859503).
Exact audit timestamp: `2026-10-03T09:06:04.677454+00:00`.

All 913 reactions and 879 compartment-specific metabolites were audited using exact fractions of the decimal values encoded in the JSON file. An independent local recalculation reproduced all 913 elemental and charge residuals. The downloaded source-model bytes reproduce the baseline Git blob hash above.

The separate audit branch adds `scripts/audit_reactions.py` and invokes it from the existing MEMOTE runner for the pinned baseline JSON companion only. The workflow's adapter tests and existing reference-profile simulation succeeded. Fresh MEMOTE completed with findings, exit code 1; its failures were not hidden. No model formulas, charges, stoichiometric coefficients, bounds or objective coefficients were changed. Main was not modified.

## Scope and method

The model contains 711 single-compartment internal reactions, 132 multi-compartment reactions, 48 exchanges, 21 demand/sink reactions and one biomass reaction. Thus 843 are non-bookkeeping reactions and 70 are boundary/biomass bookkeeping reactions.

All reactions remain in the output, including their residuals. Bookkeeping reactions are separated, not silently discarded or repaired as enzymes. Biomass still needs a separate composition/polymerization/dry-weight ledger.

Residual convention is products minus reactants: each elemental residual is `sum(S_ij * atoms_i)` and charge is `sum(S_ij * charge_i)`. Arithmetic is exact, with no tolerance used to hide small errors. Global elemental/charge checks retain compartment-specific participants.

R/X groups are tracked symbolically. Their cancellation does not establish complete molecular identity or carrier electron capacity. Of 879 metabolites, 775 have defined-element formulas and 104 have symbolic formulas. No missing or unparseable formula/charge was found by this parser; data presence does not authenticate chemical correctness.

## Results for 843 non-bookkeeping reactions

| Test | Result | Count |
|---|---|---:|
| Elements | Exact balance with defined-element formulas | 740 |
| Elements | Conditional symbolic balance with R/X groups | 102 |
| Elements | Exact imbalance | 1 |
| Charge | Exact balance | 833 |
| Charge | Exact imbalance | 10 |
| Both | Defined-element and charge pass | 736 |
| Both | Conditional symbolic and charge pass | 97 |

There are ten distinct exact-defect reactions because the single elemental defect also has a charge defect. Six permit nonzero flux by their bounds; four are disabled. Permitted flux does not mean measured or newly calculated nonzero flux.

## Exact defects

| Reaction | Element result | Exact charge residual | Baseline bound direction |
|---|---|---:|---|
| MC_Average_FattyAcid | FAIL: C, H, O | -0.001 | Reversible |
| APG3PAT_MCi | Pass | +0.001 | Forward only |
| G3PAT_MCi | Pass | +0.001 | Forward only |
| CYP460ipp | Pass | +2 | Forward only |
| HAORipp | Pass | +2 | Disabled |
| PFOR | Symbolic balance | +1 | Forward only |
| POR_syn | Symbolic balance | -2 | Forward only |
| ACCOAC_1 | Symbolic balance | -1 | Disabled |
| BTNC | Symbolic balance | +1 | Disabled |
| ASNTRAT | Symbolic balance | +1 | Disabled |

`MC_Average_FattyAcid` consumes fractions summing to 0.999, whose combined elemental composition is C16.041 H31.055 O1.998 per written reaction. Its product is encoded as C16041H31055O1998 with coefficient 1 and charge -1. Exact residuals are C +16024.959, H +31023.945, O +1996.002 and charge -0.001.

An algebraic diagnostic changing the product coefficient 1 to 0.001 closes elements but leaves charge +0.998. This is not an accepted correction and no modified model was saved. Reconcile the average-fatty-acid, acyl-CoA and downstream lipid unit/charge definitions jointly; normalizing the fractions alone is also not an evidence-supported resolution.

For charge-only failures, inserting protons would disturb the already balanced hydrogen count. Review the carrier or metabolite definitions and reaction identity using chemical evidence, propagating any approved changes consistently. Priorities include the lipid pools; cytochrome oxidation states and product identities in CYP460ipp/HAORipp; flavodoxin/ferredoxin conventions in PFOR/POR_syn; paired carboxybiotin carrier definitions in ACCOAC_1/BTNC; and aminoacyl-tRNA definitions in ASNTRAT.

## Roundoff versus genuine defects

Fresh MEMOTE has seven mass flags. Six are eliminated by exact arithmetic: `APG3PAT_MCi`, `G3PAT_MCi`, `MC_AFAA`, `PGSA_MCi`, `PHCYT_MCi`, `PSSA_MCi`. Only `MC_Average_FattyAcid` remains elementally imbalanced.

This does not clear APG3PAT_MCi or G3PAT_MCi of their real charge residuals of +0.001. Of eleven raw charge flags, MC_AFAA is the only roundoff-only flag; ten exact charge discrepancies remain.

## Identity checks beyond balance

`XANt2pp` is named as xanthine transport but its encoded equation is `gua_p + h_p --> gua_c + h_c`, identical to `GUAt2pp`. Both have bounds -1000 to +1000. Thus it conserves elements/charge but the written substrate is guanine, not the named xanthine. Resolve identity and supporting evidence before accepting its database mapping or changing the equation.

`CYP460ipp` and `HAORipp` also have identical equations despite distinct identities and bounds. This is a review flag, not automatic permission to delete either reaction.

## Direction/reversibility inventory

| Encoded bounds | All 913 reactions | Non-bookkeeping 843 |
|---|---:|---:|
| Forward only | 630 | 590 |
| Reversible | 215 | 195 |
| Reverse only | 1 | 0 |
| Disabled (both bounds zero) | 67 | 58 |

Reversible means lower < 0 < upper. Forward-only means lower >= 0 and upper > 0; reverse-only means lower < 0 and upper <= 0. A fixed nonzero flux is separately recorded. Invalid bounds were not found.

The sole reverse-only reaction is `EX_ch4_e`, bounds -18.46 to 0. Its negative exchange flux represents methane uptake; it is not a biochemical enzyme demonstrated to run backwards. Disabled does not mean irreversible. Allowed directions are model constraints, not proof of physiological reversibility.

The fresh MEMOTE stoichiometrically balanced-cycle diagnostic lists 51 participating reaction IDs. This is not 51 distinct cycles or evidence of cycles under the SYMBIONT operating profile. Diagnostic constraint changes must be taken into account. The full participant list is in the fresh MEMOTE artifact and the accompanying review workbook.

## MetaCyc coverage — candidates only

| Inherited reaction annotation state | Count |
|---|---:|
| Exactly one candidate | 464 |
| Multiple candidates | 46 |
| No candidate | 403 |
| Any candidate | 510 |
| Independently compared with a loaded MetaCyc release | 0 |

For metabolites, 624 have one candidate, 102 have multiple candidates and 153 have none. As one ambiguity, h2o_c carries OH, OXONIUM and WATER candidates: selecting the first identifier would not establish correct identity.

Actual MetaCyc reaction records and a versioned bulk dataset could not be retrieved during this audit. Official Pathway Tools format documentation was accessible, but documentation is not the reference database. Every reaction's reference equation and reference direction therefore remain explicitly unverified; inherited annotations were not upgraded to confirmed mappings.

To complete the reference layer, supply an authorized, release-identified MetaCyc export containing `compounds.dat` and `reactions.dat`, preferably also `enzrxns.dat` and `pathways.dat`. Authenticate compounds, formulas, charges and protonation states; resolve ambiguous mappings; compare complete stoichiometry with scale/orientation handling; then compare reference direction evidence with model bounds. Reverse the direction interpretation when the matched equation orientation is reversed. Retain proton, water and compartment distinctions rather than removing them just to obtain a match.

Model-specific biomass, exchanges and averaged pools need documented definitions/applicability, not fabricated exact MetaCyc matches. No reaction is currently certified as MetaCyc-verified by this audit.

## Reproduce

```bash
python scripts/audit_reactions.py --self-test
python scripts/audit_reactions.py --model ModelFiles/json/iMcBath.json --output reports/generated/reaction-audit
```

A process exit of zero means this read-only audit finished. Inspect explicit PASS/FAIL/conditional statuses. The command does not download MetaCyc or authenticate reference directions.

## Sources

- [Pinned baseline model](../ModelFiles/json/iMcBath.json), with the immutable commit and hashes specified above.
- [Executed workflow](https://github.com/chernushkindm-lab/symbiont-imcbath/actions/runs/37111859503), private memote-audit artifact including exact audit, source model and fresh MEMOTE metadata.
- [Prior chemistry review](../reports/failure-review/chemistry-details.json), corroborating inherited defects.
- [Official Pathway Tools data-file documentation](https://bioinformatics.ai.sri.com/ptools/flatfile-format.html).
- [Official COBRApy reaction API](https://cobrapy.readthedocs.io/en/latest/autoapi/cobra/core/reaction/index.html).

A passing encoded conservation check alone does not establish correct identity, physiological direction, absence of energy-generating cycles or agreement with experiments. Quantitative biological release remains unapproved by this audit.
