# SYMBIONT adapter: scope and contract

This repository supplies a standalone iMcBath model component and an explicit
constant-volume dynamic replay. It is not a plant connection or a historical
72-hour reproduction. The linked SYMBIONT report was available as narrative;
its raw workbook, normalized interval package, formula lineage and original
scripts have not been supplied to this component. The example is wholly
synthetic, including its observation values. It tests the interface, not a
historical prediction.

## Run or call the component

```powershell
symbiont-imcbath replay examples/replay-input.json --profile symbiont-reference --output reports/synthetic-replay.json
```

```python
import json
from symbiont_imcbath.core import load_baseline, apply_profile
from symbiont_imcbath.replay import replay_document

with open("examples/replay-input.json", encoding="utf-8") as handle:
    forcing = json.load(handle)
model, model_provenance = apply_profile(load_baseline(), "symbiont-reference")
result = replay_document(forcing, model=model)
# Persist model_provenance alongside result for an application-managed run.
```

The replay requires an explicitly configured ammonium-only model. The unchanged
published baseline has nitrate uptake open and is rejected by replay, including
a direct `replay_document(forcing)` call or CLI use without an appropriate
`--profile`. Apply `symbiont-reference` as above, or supply a custom profile that
explicitly closes other nitrogen inputs. Replay never silently changes the
nitrogen-source medium. The reference profile also explicitly closes import
through the inherited `SK_cyan_c` cyanide boundary sink. The
`symbiont-reference` profile is an explicit model
assumption, not an experimentally calibrated strain model. JSON model profiles
control reaction bounds and stoichiometric coefficients; the replay JSON controls
physical forcing and state. The solver method defaults to pFBA at maximal growth;
`method="fba"` selects ordinary FBA. Degenerate optima can change nitrogen uptake,
so record the solver method with a run.

## Canonical JSON quantities

Every numerical physical input uses this object, including times and fractions:

```json
{"value": 10.0, "unit": "L", "provenance": "measured", "source": "Workbook: AJ385; instrument record identifier"}
```

`provenance` is exactly `measured`, `derived`, or `synthetic`; `source` is required
nonempty text. A derived field's source should name its formula, input cells,
chemical reporting basis and version. Synthetic values must state the assumption
in `source` or an optional `note`. Provenance records are declarations: the
adapter cannot independently certify them. It preserves the input and emits a
flat `quantity_registry` for downstream auditing.

Only the units below are accepted. Convert other units explicitly before calling
the adapter; a numeric value with a different unit is an error. Missing fields,
nonfinite numbers, negative physical inputs, fractions outside [0,1], unknown
fields and inconsistent interval boundaries are rejected before solving.

| JSON field | Unit and meaning |
| --- | --- |
| `schema_version` | Integer `1` (schema marker, not a physical quantity) |
| `time_step` | `h`; requested maximum Euler step |
| `gas_basis.molar_volume` | `L/mol`; shared inlet-flow reference basis |
| `gas_basis.reference_conditions` | Text declaring temperature, pressure, wet/dry basis and source |
| `initial.time` | `h`; start on a common nonnegative relative time axis |
| `initial.biomass` | `g_model_biomass/L`; strictly positive initial model biomass |
| `initial.nitrogen` | `mmol_N/L`; extracellular ammonium inventory on an N-atom basis |
| `initial.volume` | `L`; actual controlled liquid volume |
| `intervals[].start`, `.end` | `h`; explicit contiguous interval, with end greater than start |
| `intervals[].volume` | `L`; actual volume, equal to initial volume in this version |
| `intervals[].gas_streams[].flow` | `L/min`; total flow of that named gas stream |
| `.mole_fractions.ch4`, `.o2` | `1`; inlet mole fractions; sum must not exceed one |
| `.availability_fractions.ch4`, `.o2` | `1`; effective available fraction of each inlet species |
| `intervals[].liquid_feeds[].flow` | `L/h`; actual delivery of a named liquid feed |
| `.nitrogen_concentration` | `mmol_N/L`; ammonium-N concentration in that feed, zero for N-free liquids |
| `boluses[].time` | `h`; exact timestamp within the replay window |
| `boluses[].nitrogen_amount` | `mmol_N`; amount of nitrogen atoms added, not concentration |
| `boluses[].negligible_volume` | Boolean `true`; explicit solute-pulse approximation |
| `boluses[].label` | Nonempty text identifying the event |
| `observations[].time` | `h`; withheld comparison time |
| `observations[].biomass` | Optional `g_model_biomass/L`; converted proxy or direct observation with declared basis |
| `observations[].nitrogen` | Optional `mmol_N/L`; assay converted to an explicit N-atom basis |

Gas-stream and liquid-feed names are required. Empty stream/feed lists mean
zero inlet delivery; they do not invent missing measurements. `boluses` must be
present, even if empty. `observations` is optional; omit absent observations,
including missing historical biomass points, rather than replacing them with
zero. Nitrogen here is extracellular ammonium available through `EX_nh4_e`,
not total nitrogen from every possible chemical species. Before solving, replay
inspects boundary reactions for nitrogen atoms and uses each reaction's
stoichiometry and flux bounds to identify input direction. Open nitrate, nitrite,
NH3, amino-acid, urea and any other non-ammonium nitrogen input is rejected,
including import through a reversible sink. This check handles exchanges written
in either direction. An open boundary input with a missing elemental formula is
also rejected because its nitrogen content cannot be verified. `EX_nh4_e` must
retain one nitrogen atom per flux unit and coefficient -1 for the ledger's units
to hold. Consequently, all permitted extracellular nitrogen consumption comes
through the ammonium exchange represented in the sole nitrogen ledger. The
output includes a `nitrogen_source_audit` record listing detected nitrogen
exchanges and other boundary reactions, formulas, stoichiometry and bounds.
This boundary check does not certify internal elemental balance or biological
validity; those remain separate model-quality checks.

`solve_fn` is an injected-solver seam for unit tests. Passing a test solver without
a model skips this model audit and explicitly labels it `not_performed`; such a
result does not establish source closure in a GEM. Normal application runs must
provide the configured model and use the model-aware solver.

## Balances and event semantics

For each normalized interval, `V` is the actual liquid volume, `X` is nominal
model biomass, `N` is extracellular mmol N/L, and named liquid feed `j` has
flow `F_j` and ammonium-N concentration `C_j`:

```text
D = sum_j(F_j) / V                              [h^-1]
F_N = sum_j(F_j * C_j)                          [mmol_N/h]
q_gas_cap = sum_s(eta_s * y_s * Q_s * 60 * 1000 / Vm) / (V * X)
                                                  [mmol/(g_model_biomass*h)]
dX/dt = (mu - D) * X
dN/dt = F_N / V - q_N * X - D * N
```

`Q_s` is inlet L/min, `Vm` is the explicitly declared L/mol, `y_s` is the
species mole fraction, and `eta_s` is effective availability. Availability is
not independently measured utilization, kLa, or a fitted transfer model. Gas
and nitrogen caps are recomputed using simulated biomass at every substep.
The three computed caps replace the supplied model's lower exchange bounds
for `EX_ch4_e`, `EX_o2_e` and `EX_nh4_e` during that solve. Thus these particular
profile bounds are not additional physiological ceilings in replay; all other
profile constraints remain in effect.

For an Euler substep of duration `dt`, the ammonia uptake cap is:

```text
q_N_cap = max(0, N/dt + F_N/V - D*N) / X
```

Accounting for dilution in the cap prevents spending nitrogen that leaves in
the same substep. Actual `q_N = -flux(EX_nh4_e)` enters the ledger; positive
exchange secretion is a negative net cellular removal. A nonoptimal solve
stops the replay and returns the last valid state, the time and solver status.
Negative nitrogen larger than `1e-10 mmol_N/L` stops the replay; smaller
roundoff corrections are recorded explicitly in the ledger.

Steps are split at interval boundaries and exact bolus timestamps. An event is
applied once at its timestamp by `N += amount/V`, after completing the preceding
step. Initial-time boluses apply before the first solve; final-time boluses enter
the final inventory without affecting preceding growth. Multiple same-time
events are additive. Earlier events belong in the independently declared initial
inventory. Event volume must be negligible under an explicit assumption; finite
bolus volume and variable volume require a different state balance.

The step size is also reduced when necessary to ensure `D*dt <= 0.5`; this keeps
the explicit Euler dilution update positive but is not an accuracy guarantee.
Repeat meaningful runs with half the step and inspect both trajectories and
inventories. The test suite checks first-order convergence against a known
growth solution and closure of the discrete nitrogen ledger. These are numerical
tests, not biological validation or evidence for a historical match.

Every saved state contains cumulative initial inventory, continuous input,
bolus input, net cellular removal, dilution loss, roundoff adjustment and closure
error, in mmol N. `steps` reports growth, caps, dilution, actual nitrogen uptake
and available solver residuals. `bolus_events` records executed events. Biomass
observations after initialization never set, correct or fit the simulated state;
observation timestamps never alter solver steps. Comparisons are calculated after
simulation using states or linear interpolation, with post-bolus inventory at
an exact event time. Values outside a stopped run's completed time range are
flagged rather than extrapolated.

## Map the referenced SYMBIONT workbook upstream

The following mapping is taken from the supplied report, not a fresh audit of
the workbook. A separate ingestion service must establish cell/formula lineage,
timestamps, chemical basis and source validity before producing this JSON.

| Reported source fields | Normalized adapter input / treatment |
| --- | --- |
| V / S / T / U: methane, air, generator gas and purity | Separate gas streams and explicit mole fractions; U is a formula estimate, so mark derived |
| P / Z / AD: medium, ammonium titrant, KOH | Named liquid feeds; normalize all to L/h, preserve actual interval totals |
| AJ: actual culture volume | Interval volume; do not inherit the report's hard-coded 10 L dilution denominator |
| AK and medium recipes | Feed ammonium-N concentration; multiply recipe by the recorded multiplier and count both N atoms in ammonium sulfate |
| W:X:Y / AA:AB:AC: bottle depletion/refills | Reconcile tare, refills, density and timing upstream; negative inferred delivery is an error requiring source review |
| AP / AO / AN and AM optical channels | Initial biomass once; later proxy values are withheld observations; preserve calibration formula and optical-channel distinction |
| Journal ammonium boluses | Explicit mmol N events after resolving stock strength, volume and timestamp |
| Journal residual nitrogen assays | Withheld observations only after resolving NH4 vs NH4-N or other reporting basis |
| R / AQ | Recompute D from actual feed/volume; D*X is a throughput proxy, not growth or integrated harvest |
| AR:AU off-gas/OTR | No uptake fitting without valid composition closure, common wet/dry basis and calibrated exhaust flow |
| D:F:G:H:I, minerals, phosphate and interventions | Context for a separate validity layer; this adapter does not fit inhibition, transfer or phosphate limitation |

For the report's hourly convention, liquid deliveries recorded in row `r+1`
belong to `[r,r+1]`, while point gas settings from row `r` are held over that
interval. Encode this convention into explicit `start`/`end` records before
replay. Do not subtract intra-hour stops a second time if interval delivery
totals already include them. A gas stop is an explicit measured/derived zero;
missing gas data is not automatically a zero.

For chemical conversion, distinguish nitrogen atoms from mass of NH3, NH4+, or
NH4OH and preserve the chosen molecular weight and certificate basis. One mole
of `(NH4)2SO4` supplies two moles of N. A stated `1 mL, 1 M` addition supplies
`1 mmol` of the named solute; it is `2 mmol_N` only for a solute with two N atoms
per molecule. The narrative alone does not resolve ambiguous journal entries.

## What remains outside this component

The reference's claimed 72-hour final biomass, 2,592 solves and half-step
differences have not been reproduced here. Reproduction requires the exact
source workbook or its privacy-filtered normalized package; timestamp/cell and
formula maps; titrant certificates and chemical basis; recipe linkage; bolus
identities and event times; initial inventory; a declared VS1/Bath equivalence;
the original model/MMO profile and solver configuration; and withheld biomass
and residual-assay series with calibration provenance.

Constant volume assumes well-mixed liquid outflow equals total liquid inflow,
with no biomass retention, decay, variable-volume storage, sample withdrawal
events, or gas-transfer dynamics. Availability factors and unmeasured inventories
remain assumptions. No biochemical coefficient is inferred from the archived
MEMOTE biomass-mass diagnostic. MEMOTE tests model quality; it does not validate
predictions, the VS1/Bath equivalence, or a plant control decision. A calibrated
online SYMBIONT service still needs acquisition, mass-to-flow reconciliation,
gas validation, an assay/calibration registry, and prospective held-out testing.

Reference design: [SYMBIONT real data GEM replay](https://docs.google.com/document/d/1XspPz6hL60vsEdvUsfcxWHRTwvjkGATJo9AOZxDgyDg/edit).
Model source: [ChristianLieven/memote-m-capsulatus](https://github.com/ChristianLieven/memote-m-capsulatus),
commit `f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160`.
