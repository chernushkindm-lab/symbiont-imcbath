# Scientific assumptions and qualification boundaries

Decision record updated 1 October 2026. This document describes the implemented scientific functions, not a claim of biological validation. Source files were read as data; no supplied notebook or mass-balance script was executed or changed.

## Authoritative user decisions

- LAB005, FA10, F10/Ф10 and YFC-10L refer to the same reactor; preserve original labels.
- Acquisition timezone is Asia/Yekaterinburg. It is distinct from the user's Moscow timezone.
- The 10 L working volume is authoritative for the present historical interpretation. Original 7–12 L entries remain evidence with conflicts. The balance engine nevertheless supports variable volume; its reference cases do not override this decision.
- The selected observation endpoint is **total dry residue**, using the supplied calibration/workbook. It is not automatically cellular dry mass and cannot directly scale cellular GEM uptake or validate a cellular kinetic state.
- DO is percent air saturation. The matching calibrated air-saturation concentration still requires probe conditions, temperature, pressure, salinity and method provenance. The user decision does not establish a universal mg/L conversion.
- The calibration workbook's displayed Flow Rate is dilution D [h^-1], not volumetric Q [L/h]. Other source columns explicitly in mL/min retain their own unit definitions. Q = D V only applies to the corresponding documented liquid stream/definition.
- The last nonempty notebook variant is the accepted conceptual structure. None of its hardcoded parameters is accepted as a fitted LAB005 measurement.
- A standalone Python worker with a Go adapter boundary and local-computer private deployment is accepted. There are no hardware control writes.

## Inventory and observable equations

The engine uses elapsed hours, liquid litres and explicitly matched g/L, mg/L or mmol/L bases. For an interval, accumulation is `(V1 C1 - V0 C0)/dt`, not `V1 (C1-C0)` subtracted from a rate. Incoming/outgoing rates are interval averages of each **flow times concentration** product. Integrated event quantities enter once, separately from continuous streams. Samples, drain/refill and additions must not also be counted as duplicate stream terms.

`inventory_balance` returns apparent disappearance. Chemical conversion, precipitation, adsorption, volatilisation and other unresolved sinks remain possible; this result is not called cellular uptake. `biomass_productivity` uses total formation divided by `integral(V dt)` and separately returns net inventory accumulation and harvest productivity. The mean volume argument represents that integral divided by elapsed time. Total dry residue formation includes any changing noncellular residue contribution. Gross cellular growth and loss are not individually identifiable from this endpoint alone.

Bottle mass increases or verified bottle changes block inferred delivery; no negative delivery is accepted. The generic solution conversion requires explicit density, purity, molecular mass and elemental stoichiometry. Unknown stream concentrations or mixed chemical bases raise a gate rather than becoming zeros.

A complete historical nutrient ledger additionally needs active bottle/recipe links, use intervals, delivered volumes, titrant concentration/density/basis, censored broth assays, and relevant sinks. Header presence and preparation dates do not supply these fields.

## Exhaust flow, gas rates and transfer

The soft-sensor report supplied with this task already concludes that no historical row is validated for dry exhaust flow. Page 6 gives the identifiability argument: inlet rates and CH4/O2/CO2 fractions supply three species equations for four unknowns (exhaust flow, methane uptake, oxygen uptake and CO2 generation). Unknown nitrogen exchange adds uncertainty. Inlet flows alone cannot uniquely recover outlet flow.

`conditional_exhaust_flow` implements `Fout = Fin - U_CH4 - U_O2 + G_CO2 - dN_total/dt`. All five intervals plus explicit assumptions are required. Its output is labelled **model_only**, with scenario bounds, never observed uptake or a statistical confidence interval. Missing closure gives **not_identifiable**. This makes the requested inlet-driven soft sensor available as a conditional calculation without pretending it creates independent information. The assumptions must account for other species, nitrogen uptake, higher hydrocarbons, leak/condensate terms and transient inventories where material.

A separate tracer estimator requires documented conservation, an informative positive fraction interval, and explicit inventory/leak correction. Nitrogen-containing remainder is blocked without evidence of nitrogen conservation. No generic claim that N2 is inert is built in. Invalid gas compositions are preserved and rejected; fractions are never renormalised to force closure. Negative inferred methane or oxygen disappearance is reported as inconsistent under the selected assumptions.

Gas rates use positive methane/oxygen disappearance and positive net CO2 production. Inventory-plus-liquid corrections are explicit. Ratios are molar OUR/MUR, MUR/OUR and CER/OUR. Methane/oxygen disappearance is not uniquely attributed to a producer organism, and CO2 percentage is not a production rate. The current engine does not infer missing composition, analyzer delay or uncertainty covariance.

`gas_volume_to_mmol_h` applies the ideal-gas equation at the **meter's stated reference** pressure, temperature and compressibility. Standard/normal flow must not be re-corrected at reactor temperature. A pressure argument is absolute, never gauge pressure. Dry/wet conversion requires independently known water content; the current rate API rejects unresolved/wet bases.

`oxygen_transfer` returns both kLa(C*−C) [mmol/(L h)] and V times this quantity [mmol/h]. Signed transfer allows stripping. Total OUR compares with total OTR only after inventory terms are justified. User-reported 700 h^-1 at 799 rpm remains a separate reference with incomplete conditions.

The supplied `kla OTR ФА-10 (2).docx` contains sulfite chemical absorption tests, not a culture-derived kLa curve. Tables 1/3 specify 10 L, 0.6 g/L CuSO4 and 1.9 g/L Na2SO3; air feeds are 10 and 20 L/min. Tables 2/4 use 300/500/700 rpm at 21.66–23.41 °C; their kLa values are 315.0611/627.2525/817.0662 h^-1 and 417.4429/774.6264/1077.7678 h^-1 respectively. C*=8.9 mg/L and oxygen density≈1.315 kg/m³ are stated. The OTR heading prints kg m^-1 h^-1, a dimensional transcription requiring review. Table 5 compares impeller configurations. These chemical-test values cannot be substituted directly for broth transfer under different temperature, gas composition, antifoam or geometry. No fitted rpm correlation is released.

## Notebook audit and independent kinetic branch

`Kinetics.ipynb` contains 17 cells and 11 nonempty code variants, at zero-based cell locators 0, 1, 3, 4, 5, 9, 11, 12, 13, 14 and 15. Execution counts are 127, 164, 168, 192, 228, 94, 48, 40, 50, 96 and 230, so source order does not describe one clean execution. The copy under `MAGIC SCRIPT/Kinetics.ipynb` has the identical SHA256.

Early variants differ in mass units, imposed pressure schedules and transfer assumptions. Cell 3 records state from the adaptive RHS. Cell 5 introduces an object with mutable pressure-control state. Late variants carry `[X, CH4, O2, CO2, pressure]`, with a 100 L demonstration vessel, approximate 24 L/mol gas conversion and hardcoded gas/pressure assumptions. Cell 15 has D=0.2 h^-1; this is not a measured net culture growth rate.

Cell 15 uses `CH4 + 1.45 O2 -> 0.52 X + 0.48 CO2` as though unlabelled coefficients were mass yields. It clips CH4 and O2 consumption separately while retaining the pre-clipping biomass growth, permits only nonnegative CH4/O2 transfer, and omits CO2 stripping despite calculating a CO2 equilibrium value. These are not accepted physical calibrations.

The refactor retains saturation kinetics and optional oxygen/CO2 inhibition as explicit nested model choices. Parameters have named mass units, are immutable, and are labelled hypothetical until fitted. One growth rate creates coupled substrate demands; growth vanishes at either depleted substrate boundary. Carbon routed to CO2 is calculated from CH4 carbon minus new biomass carbon, rather than importing an ambiguous coefficient. This demonstrates a carbon invariant for the closed numerical reference; it does **not** establish full elemental/electron conservation, identify nitrogen assimilation, validate oxygen yield, or model dissolved inorganic carbon speciation. Loss is a detritus sink; it is not silently converted into CO2.

Pressure is an input to separately documented species-specific equilibrium concentrations. No pressure controller or inherited pressure ceiling is exposed as an operating recommendation. Transfer is reversible, species-specific and capped by declared total CH4/O2 supply. Variable volume uses the inventory-consistent concentration equation. Discrete well-mixed withdrawal/refill events restart the solver exactly; empty vessels require a new segment. A pure RHS has no logging/controller side effects, and substantial negative states cause failure. Tiny numerical excursions alone are clipped within declared tolerances.

`kinetic_reference_case()` is a synthetic closed numerical test with no transfer, feeds or pressure control. It returns labelled rows, parameters, carbon residual and solver tolerances for the API demonstration. It is neither a LAB005 replay nor a forecast qualification. Historical cellular kinetics currently lacks a supported dry-residue observation bridge, methane solubility, matched transfer boundary conditions and identifiable kinetic parameters. Adding N/P inhibition terms or fitting many parameters to sparse history is therefore blocked.

## Scoring and forecast qualification

Pairs require the same observable, run/segment, forecast origin and interval. Synthetic/imputed ground truth and a target used as a model constraint are excluded. Bias, MAE and RMSE use interval duration; harvested mass error additionally uses mean volume. Relative gaps are suppressed below a declared positive threshold. Capacity shortfall and forecast error have distinct labels and denominators. Prediction-interval coverage/width are returned only when intervals actually exist.

The available baseline engine uses each run/segment separately, a fixed trailing 24-hour training window, persistence and a log-linear residue trend. The latter is an empirical effective residue-rate baseline, not an independently calibrated mechanistic growth parameter. Features must have both event and availability time no later than the forecast origin. Unknown availability produces explicit exclusions. Forecasts use target tolerances and stale-data gates; there is no cross-event smoothing, random row split, ensemble tuning or synthetic validation target. Point-concentration metrics are labelled point metrics separately from interval-productivity metrics.

Shared OD/calibration uncertainty correlates inputs and observed residue; errors on these labels do not establish independent gravimetric validation. Rolling-origin results also overlap and are correlated. The code does not report fabricated confidence intervals. Current historical forecast qualification can remain blocked while deterministic implementation tests pass. A new model may only be accepted after frozen preprocessing/calibration, genuine reporting-time information, matched boundaries/observables and held-out evaluation.

## Computational audit of supplied scripts

- `Mass_balance_with_medium_analytics.py` lines 179–181 and `FINAL_MASS_BALANCE_WITH_FULL_STATISTICS_14-06.py` lines 185–187 subtract `V × delta C` directly from mg/h rates, omit division by elapsed time, and omit changing-volume inventory effects.
- The first script lines 24/42/70 and the second lines 25/43/76 forward-fill date/timestamp or flow values without expiry. Resulting synthetic times or stale values cannot enter a forecast as if measured.
- First script lines 85–86 and second lines 91–92 use nearest joins within 45 minutes; this can use later assays retrospectively and leaks into forecasts unless availability is gated.
- First script line 120 and second line 126 interpolate concentrations by row position across interior gaps, without event boundaries or physical elapsed-time treatment.
- Missing salt masses are replaced by zero at lines 61/67; flows are filled with zero, and default titrant concentrations enter formulas. These are assumptions, not analytical evidence. Acid solution volume requires density/purity before salt-to-element conversion.

Original calculations remain an auditable historical source. They are not executed in the new ingestion or scientific worker.

## Snapshot hashes

| Source in 04_Protocols_and_Methods | SHA256 |
|---|---|
| Kinetics.ipynb (also MAGIC SCRIPT copy) | `6eaaf9ff6cb0636b4da5a219bf7b7b0bce901964fc0f5c278bf2439ca2f478ff` |
| kla OTR ФА-10 (2).docx | `eeea9384b746da6f242c0f1256ad0ff3ebf9144c5edb131bf402b2bda488f7ee` |
| SYMBIONT_Exhaust_Soft_Sensor_Report.pdf | `bac1693341e3c3ddb2ed5163edf149f9eb8c2a4da2bd70565ecb27f8562f74e7` |
| Mass_balance_with_medium_analytics.py | `07b4403dc7fd8295b08dc3fea1bcd88fe8ccf47616d3a1400a12a6d2026bb5f8` |
| FINAL_MASS_BALANCE_WITH_FULL_STATISTICS_14-06.py | `9b453d59ec35761b8182c79c46b2ab34eedf07448b55957d9090910ebc03d3b3` |

## Verification on this checkout

On 1 October 2026 the 27 tests in `m10/tests/test_science.py` passed in the project scientific environment. They cover variable-volume/irregular-time inventories, event mass accounting, bottle resets, chemical and ideal-gas units, invalid gas compositions, soft-sensor identifiability, nitrogen tracer conservation gates, transfer rate bases, pure coupled ODE dynamics, substrate depletion, carbon conservation, CO2 stripping, exact event boundaries, analytic washout/convergence, censoring, cellular-residue gates and future-information exclusion.

The synthetic closed kinetic reference produced a maximum carbon residual of `1.417754802446325e-13 g`, below the predetermined `1e-8 g` numerical tolerance, with BDF `rtol=1e-7` and `atol=1e-10`. This is implementation consistency. It is not historical forecast accuracy or full elemental model validation. Input-gate completion still leaves `qualified_forecast=false` until independent held-out evaluation is accepted.

## Historical algebraic replay

The source-linked `historical_analysis.analyze_observations` helper was run against both imported snapshots independently, using the selected OD-to-total-dry-residue calibration and the user-authoritative 10 L volume. It uses exact-time D/residue pairing, a maximum 4-hour inventory interval, and excludes cross-segment or calibration boundaries. Six additional helper tests passed, covering source IDs, intervals, shared calibration, boundaries and hypothesis links.

| Quantity | August run | May run |
|---|---:|---:|
| Selected OD-derived residue points | 664 | 412 |
| Within-segment inventory intervals | 449 | 359 |
| Exact-time conditional D × residue proxies | 616 | 360 |
| Paired legacy ASV comparisons | 664 | 397 |
| Missing/nonunique exact-time D exclusions | 48 | 52 |

The maximum D × residue proxies were 2.395608408 and 2.446535685 g/(L h), respectively. These values are conditional calculations using source-derived D. They are not independently measured harvest or biological formation, and do not establish or refute the May report's 3 g/(L h) claim. The legacy/selected residue ratio spans 0.9971–11.7453 in August and 1.0247–47.3254 in May; this quantifies disagreement between derived channels, not error against independent ground truth.

Example provenance: the first August inventory interval uses protocol AP3/AP4 and normalized observation IDs `obs-a5f1c52894ae821a54128082` and `obs-e3ff54bb04ab5959a133a0f4`, with calibration `F10-total-dry-residue-65ceafb0486f`. Every derived interval/proxy carries source locations, actual parent IDs and inherited QC, including calibration extrapolation where present. Net biological formation remains null without verified stream terms. `build_hypotheses(run)` attaches these kinds of source records and operator spans to eight competing diagnostic alternatives; their ordering is a review sequence, not causal ranking.
