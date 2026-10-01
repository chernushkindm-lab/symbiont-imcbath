# M10 model audit and computational scope

The M10 service calls the existing `symbiont_imcbath.core` loader, versioned profiles and solver. It preserves the upstream artifacts and uses their published biomass normalization. The checkout is newer than the prompt snapshot: the existing repository already contains a modern Python adapter, reference profile, constant-volume replay, tests and a detailed MEMOTE failure review. None of that prior evidence is silently presented as newly executed M10 validation.

Bath GEM used as a conditional surrogate for VS1; equivalence is not experimentally established.

## Identity and reproducibility

The source model is Christian Lieven's iMcBath, upstream commit `f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160`. The implementation checkout at the start of this work is `417fa2bb331eec7a2b49350eb10b3604369b55fd`. Runtime uses the exact JSON artifact; MEMOTE uses its SBML counterpart. `scripts/audit_m10_model.py` loads JSON, SBML and YAML and compares reaction/metabolite/gene identifier sets, stoichiometry, bounds, objective, GPR, metabolite formulas, charges and compartments. Its tolerance is absolute and relative `1e-12`. Annotation completeness remains a separate MEMOTE concern. A map of 17 verified reactions and their original bounds is in `configs/reaction_map.yaml`.

| Artifact | SHA-256 |
| --- | --- |
| JSON | `92ae700bd42fae2339a1b2ad2d3d6c6011e7004d163bf4c708f4bed0b944bdda` |
| SBML | `c2591237d8968164faeb8fafe741a9a42f95131b919086d5eb1a14b159fee092` |
| YAML | `ade8aa1a71d1fb406f7ab85aab40b51477876720eff0a4558d0eb0e777836038` |

Rerun from the repository with its installed scientific runtime:

```text
python scripts/audit_m10_model.py
python scripts/run_memote.py --output reports/m10-audit
python -m pytest m10/tests/test_gem.py
```

Machine-readable results are retained in `reports/m10-audit/model-integrity.json`, `reference-regression.json`, `run-metadata.json`, `junit.xml`, `memote-results.json`, `memote-scored.json` and `memote.html`. The MEMOTE command intentionally returns nonzero for inherited findings. It is not an application crash or permission failure. `model_audit_summary()` distinguishes a new run from an inherited repository audit and reports integrity, solver, experimental and forecast status separately.

## Supported calculations and gates

| Output | Status | Meaning and release gate |
| --- | --- | --- |
| Immutable model loading, numerical regression | Supported after regression passes | Software reproduction of a declared reference; no fitting to LAB005 observations. |
| Source-linked conditional uptake-capacity scenario | Conditional | Every CH4/O2/NH4 bound must be supplied with positive uptake interval, exact units and source. P/Cu/Fe may be supplied; otherwise their inherited permissive bounds are disclosed. |
| Gross capacity in g modeled biomass/(L h) | Conditional only with mapping | Requires explicit dry-residue-to-modeled-biomass factor and evidence/assumption label. A factor is not silently set to one. |
| Absolute cellular DCW, producer biomass, or total dry-residue prediction | Blocked from equivalence alone | Whole-broth dry residue includes unassigned solids; mixed-culture attribution and biomass normalization remain unresolved. |
| Historical measured flux reconciliation | Blocked when uptake or normalization evidence is absent | Requires accepted cellular uptake intervals, parent observations and a validated biomass/producer-attribution mapping. Inlet supply and an uncalibrated exhaust soft sensor are not measured uptake. |
| FVA and finite perturbation sensitivity | Conditional | Feasible alternatives at optimum and dependence on bounds. They are not confidence intervals or causal diagnoses. |
| Historical GEM dynamic forecast | Data-limited | Existing constant-volume `replay_document` is reusable only after transfer availability, N inventory, flows, modeled biomass and event timing are supported. It rejects variable-volume windows. |
| Validated VS1 forecast or operating optimum | Not qualified | Needs independent held-out observations, normalization, phenotype, medium and transfer validation. |

No calculation substitutes a concentration for an uptake flux. The cap unit is `mmol/(g_model_biomass h)`; negative exchange flux denotes uptake for the verified coefficient -1 exchanges. For positive uptake interval `[lo, hi]`, the model receives bounds `[-hi, -lo]`. Unavailable or contradictory evidence returns a blocked status with null results. Solver infeasibility is not converted to zero growth. Missing a required CH4/O2/NH4 cap does not expose a default unlimited supply.

## Scenario and scientific limits

The existing `symbiont-reference` profile is an explicit synthetic architecture scenario: sMMO enabled, two pMMO routes disabled, ATPM fixed at 8.39, CH4/O2/NH4 caps 16/28/2.3 and nitrate/nitrite/cyanide supply closed; N2 is already closed. Its expected biomass flux is `0.2255827702718434 h^-1`, with regression tolerance `1e-9 h^-1`. A new boundary audit found that this inherited profile also leaves `EX_co_e` carbon-monoxide import open (-1000 to 1000). M10 explicitly closes CO import in its versioned window overlay; the existing profile and source files remain unchanged. The stored reference solution had zero CO import, so this is a scenario-source correction rather than evidence of a particular LAB005 metabolic process. M10 replaces the three uptake bounds with the supplied window scenario, records profile hashes and changes, and audits every boundary for unexpected carbon or nitrogen imports. P, Cu, Fe and other inherited mineral permissions are not measurements. The code does not select MMO from total copper or silently repair chemistry to improve a fit.

Growth is read from `BIOMASS_Mcapsulatus`, never from the pFBA summed-flux objective. Numerical feasibility follows the existing GLPK adapter (solver feasibility tolerance `1e-9`; reported residual gate `1e-7`). The reference is a numerical regression, not a reproduction of every experiment in the 2018 paper. The paper examines Bath physiology and alternative electron-transfer mechanisms; it does not establish VS1/LAB005 equivalence. [Lieven et al., 2018](https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2018.02947/full).

The inherited detailed review identifies biomass-normalization, material fatty-acid representation, charge, blocked-reaction, cycle and annotation findings, plus test-suite defects and coverage gaps. The approximate biomass mass diagnostic 0.902 is not an empirical calibration multiplier; M10 does not apply its reciprocal. The complete failure interpretation remains in [MEMOTE_FAILURE_REVIEW.md](MEMOTE_FAILURE_REVIEW.md).

## API boundary

`m10.metabocore.gem.capacity(request)` is a deterministic scientific call apart from its audit timestamp. Inputs include schema version, run/window identity, mode, uptake provenance and optional mapping. It returns a request hash, immutable artifact hashes, versioned profile history, active exchange bounds, pFBA solver evidence, binding upper uptake bounds and qualifications. Requested FVA is bounded to at most eight mapped reactions and one process. Optional finite perturbations increase each declared principal cap by at most 20 percent and retain the resulting solver status. Source observations and models are never mutated.

`reference_regression()` runs the pure declared numerical reference. `model_audit_summary()` reads audit artifacts without executing the suite. A local web or Go gateway can call these functions through the service's versioned job boundary; it must retain the returned qualifications and labels.

The existing adapter's deterministic replay is the dynamic GEM implementation boundary. It must not receive total dry residue under a renamed model-biomass unit. M10 capacity multiplied by observed state is visibly a capacity calculation and is never used as a free-running forecast or scored as an independent observation.

COBRApy documents the flux-bound meaning of medium values and the distinct pFBA objective. Its example dFBA notebook explicitly remains an illustrative implementation. [Media](https://cobrapy.readthedocs.io/en/latest/media.html), [FBA/pFBA/FVA](https://cobrapy.readthedocs.io/en/latest/simulating.html), [dFBA](https://cobrapy.readthedocs.io/en/latest/dfba.html). MEMOTE's benchmark commands assess model quality separately from process prediction. [MEMOTE](https://memote.readthedocs.io/en/latest/getting_started.html).

## Windows path compatibility

The first fresh audit launch verified the correct SBML hash but libSBML reported `File unreadable` for the native path containing Cyrillic characters. This is preserved separately as `reports/m10-audit/unicode-launch-metadata.json` and its console log. The MEMOTE runner now retries only that specific Windows non-ASCII path/read failure with an exact, hash-verified temporary ASCII-path copy, removes the temporary file after loading, and records both the original loader notification and workaround in run metadata. Scientific model-validation failures do not trigger that retry. The format comparison passes a Python `Path` to COBRApy so it reads SBML through Python's Unicode-safe text reader. The original model remains unchanged.

## Verified M10 findings

The functional comparison confirms **JSON and SBML agree** for all audited IDs, stoichiometry, bounds, objective, GPRs, formulas, charges and compartments. The preserved **YAML is a different historical model state**: 898 reactions and 877 metabolites, compared with 913 and 879 in JSON/SBML; all retain 730 genes. The YAML lacks 15 reactions and the `cyan_c` and `tcynt_c` metabolites, and contains nine bound differences across eight reactions. In particular it opens N2, closes nitrate, enables `PMMOipp` and disables `SMMOi`; it also differs in `GAPD`, `GAPDH_nadp`, `GLNS` and `PGK`. These are real version differences, not a line-ending or rounding issue. The full ID and before/after lists are in `model-integrity.json`.

All three files still match their exact pinned upstream hashes. This establishes provenance, not equivalence. **JSON is the selected runtime and its equivalent SBML is the audit artifact. YAML is retained as historical evidence and is excluded as an interchangeable runtime.** The integrity helper returns exit code 1 to expose the all-encoding mismatch; it does not silently redefine that mismatch as a pass. Its separate `runtime_audit_pair_consistent` field is true.

The pure numerical reference reproduces biomass flux **0.22558277027184387 h^-1**, within its fixed `1e-9` regression tolerance. The M10 GEM/loader suite reports **17 passed**, zero failures and zero errors, in `gem-tests.xml`. Tests cover model-byte integrity, reference regression, pFBA biomass extraction, explicit dry-residue mapping, missing-input/reconciliation gates, unit/sign errors, starvation versus valid zero growth, FVA labeling, finite perturbations and the same-byte Windows loader retry. These implementation checks do not qualify biological forecasts.

A second launch issue arose because pytest attempted to infer a collection root across the G: repository and C: runtime, then scanned an inaccessible Windows junction. The runner now scopes pytest's `rootdir` and `confcutdir` to MEMOTE's own test directory. This changes collection locality, not the test selection or scientific assertions; launch diagnostics remain separate from the completed audit's model findings.

The initial multiprocess consistency run subsequently stalled with unchanged parent/worker CPU. Its interruption record and console are preserved as `pool-interruption.json` and `pool-interrupted-console.txt`; it is not counted as a completed model audit. The runner now sets the documented `cobra.Configuration().processes = 1`, retains the 10-second per-solve timeout, and logs individual test progress. This runs the same complete suite deterministically without the Windows pool; no assertion, bound, tolerance or test selection is relaxed.

## Completed fresh MEMOTE run

The single-process run completed from **2026-10-01 21:37:40 UTC to 21:41:37 UTC** (00:37-00:41 on 2 October in Moscow). It records **147 cases: 80 failed, 59 passed, 8 skipped and zero JUnit errors**, with exit code 1 and status `completed_with_findings`. Its weighted total score is **54.05430766844975% (54.05%)**. SBML loading completed with no recorded validator errors/warnings after the native-path workaround. This is a completed audit with inherited findings, not a clean audit pass.

The new score differs slightly from the prior repository run's 54.07678692622553%. `comparison-to-prior.json` records the complete metric delta: the blocked-consumption list contains 368 metabolites rather than 369 (adds `adcobhex_c`, removes `co2dam_c` and `thrp_c`), and the unbounded-flux fraction changes while its 42 reaction IDs remain identical. Pass/fail/skip classifications do not change. These run-level diagnostic differences are retained without claiming a biological change or predictive accuracy; the current run uses a different, explicit single-process configuration. No model coefficients or test tolerances were changed to match an earlier score.

The raw HTML, machine-readable result and score, JUnit and metadata in `reports/m10-audit` are the fresh completed artifacts. `memote-single-console.txt` belongs to this completed execution. Earlier launch failures and the interrupted pool run have separate names and do not count toward its 147 scientific test cases. The older case-by-case failure review remains useful, with the two numerical metric deltas above made explicit.
