# Validation evidence and limits

A fresh MEMOTE audit of the unchanged upstream SBML completed with a **54.08% total score**, **80 failed**, **59 passed**, and **8 skipped** cases out of 147. There were **zero test errors**. Exit code 1 records test failures; this is a completed audit with findings, not a clean MEMOTE pass. Adapter software tests and a successful flux solution are separate evidence and do not remove these inherited model findings.

## Audit identity and artifacts

The audited model is `ModelFiles/xml/iMcBath.xml`, upstream commit `f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160`, SHA-256 `c2591237d8968164faeb8fafe741a9a42f95131b919086d5eb1a14b159fee092`. The audit started at **2026-10-01 18:42:55 UTC** and finished at **18:50:46 UTC**; JUnit reports 444.824 seconds for the test suite. The environment was Windows 11, Python 3.12.14, MEMOTE 0.17.0, COBRApy 0.30.0 and GLPK via swiglpk 5.0.13, with a 10-second solver timeout. Full versions and SBML validator notifications are in [run metadata](../reports/baseline-audit/run-metadata.json).

- [Interactive MEMOTE report](../reports/baseline-audit/memote.html)
- [Scored results](../reports/baseline-audit/memote-scored.json)
- [Raw results](../reports/baseline-audit/memote-results.json)
- [JUnit case outcomes and skip reasons](../reports/baseline-audit/junit.xml)

These are new run artifacts. The root `MCapsReport.html` and `index.html` remain inherited historical reports. Model identity and the distinction between historical and new evidence are documented in [UPSTREAM.md](UPSTREAM.md).

## What the score measures

| MEMOTE section | Score |
| --- | ---: |
| Consistency | 97.76% |
| Metabolite annotation | 82.55% |
| Reaction annotation | 79.36% |
| Gene annotation | 0.00% |
| SBO annotation | 9.98% |
| **Weighted total** | **54.08%** |

The underlying total is `0.5407678692622553`. MEMOTE weights categories; this is neither `passed / total` nor a measure of prediction accuracy. Annotation deficiencies materially affect the score: 21 metabolites and 53 reactions lack any annotation, all 730 genes lack gene-product annotations, and 858 metabolites and 772 reactions lack SBO terms. These are metadata deficiencies, not evidence that all those entities have incorrect chemistry. Conversely, the high consistency section does not establish that every chemical equation or the biomass definition is correct. See [MEMOTE.md](MEMOTE.md) for interpretation.

## Major model findings

| Check | Fresh result | Interpretation |
| --- | --- | --- |
| SBML validation | No validator errors or warnings recorded; SBML Level 3 Version 1 and FBC presence checks pass | The file is readable and passes these format checks. Annotation parsing and semantic completeness are assessed separately. |
| Stoichiometric consistency | Pass; zero unconserved metabolites reported | This checks the network's mathematical conservation structure. It does not verify the particular chemical formula assigned to every metabolite. |
| Biomass normalization | Fail; component-mass diagnostic **0.9024111134789822** | The expected normalization is approximately 1. Audit precursor formulas, coefficients and maintenance accounting before interpreting biomass as calibrated dry-cell weight. |
| Chemical mass balance | 7 of 843 internal reactions flagged, 0.83% | Inspect numerical residuals and the underlying reaction/formula definitions; the flags have different magnitudes. |
| Charge balance | 11 of 843 internal reactions flagged, 1.30% | Both nontrivial charge discrepancies and small residuals are present. |
| Biomass production | Default-medium growth test passes at **0.1780041817185448 h⁻¹** | This is the upstream default condition, distinct from the SYMBIONT reference profile. |
| Biomass precursor production | Pass in both default and open-medium tests | No blocked biomass precursors were identified by these tests. This differs from the inherited historical report. |
| Universally blocked reactions | 256 of 913 flagged, 28.04% | The open-boundary analysis still finds reactions unable to carry flux. This includes the consequences of retained internal bounds and does not by itself establish missing genes or pathways. |
| Stoichiometrically balanced cycles | 51 reactions flagged | Internal cycling requires review. This finding is distinct from an energy-generating cycle. |
| Energy-generating cycles | 11 energy-couple cases pass; 5 are skipped | No erroneous energy-generating cycles were detected for the tested couples under this test's setup. This does not cover the skipped couples or all possible thermodynamic defects. |

All metabolites pass the formula-presence and charge-presence tests, so the balance findings cannot simply be attributed to absent formula or charge fields. Inspection of the audited SBML shows one substantial elemental imbalance in `MC_Average_FattyAcid`: the signed elemental residuals are C `16024.959`, H `31023.945`, and O `1996.002` per reaction extent under the encoded formula/coefficient convention. This needs a targeted audit of the average-fatty-acid representation. No automatic correction has been applied.

The other six mass-balance flags (`PHCYT_MCi`, `MC_AFAA`, `PGSA_MCi`, `APG3PAT_MCi`, `PSSA_MCi`, and `G3PAT_MCi`) have elemental residuals at floating-point roundoff scale, at most about `7.2e-15` in the inspected calculation. MEMOTE 0.17.0's mass/charge helpers compare residuals with exact zero, so retain the reported count while distinguishing numerical noise from a material chemical discrepancy. Charge flags include unit-scale discrepancies in `PFOR`, `CYP460ipp`, `ACCOAC_1`, `BTNC`, `HAORipp`, `ASNTRAT`, and `POR_syn`, and smaller residuals in average-lipid-related reactions. The complete flagged ID lists remain in the raw and scored results.

The energy-cycle result should be read from its pass/skip outcomes and empty reaction lists. Its generated message template contains wording about producing energy even when the returned list has zero reactions; that wording is not evidence of a detected cycle.

Do **not** use `1 / 0.9024111134789822` as an automatic biomass correction. It would change the relationship between flux, precursor consumption and energy demand without establishing which model definition is wrong. The delivered baseline retains the upstream units and coefficients.

## What was skipped

The run supplied no custom experimental phenotype dataset. The growth-phenotype and gene-essentiality comparisons were therefore skipped because their experiment parameter sets were empty. Copying the upstream `data/` files into this repository does not mean those experiments were rerun. This audit provides no new experimental growth or gene-essentiality validation.

Five energy-couple cases were skipped because the corresponding metabolites were not found: `MNXM191`, `MNXM223`, `MNXM7517`, `MNXM12233`, and `MNXM558`. The thermodynamics test module was also skipped: MEMOTE's recorded reason says these tests are disabled pending an equilibrator-api upgrade. These account for all eight skipped entries in [JUnit](../reports/baseline-audit/junit.xml).

## Adapter and reference checks

The final local adapter suite reports **77 passed, 2 skipped, 0 failures** in [adapter-tests.xml](../reports/adapter-tests.xml). The two symlink-specific export tests are skipped because this Windows session cannot create symbolic links; their test cases remain available on platforms that can. These tests validate implementation behavior, not the scientific validity of the source model. Coverage includes immutable baseline loading, profile validation, absolute coefficient replacement, objective/biomass separation, exports, nitrogen balances, event timing, withheld observations, infeasible solves, and time-step sensitivity.

Independent implementation review identified untracked nitrate uptake in a default replay, export/response path collisions, duplicate replay JSON keys, and uptake reporting after exchange-stoichiometry edits. Their corrections and regression cases belong to the adapter validation: nitrogen-source auditing must reject undeclared inputs, JSON parsing must reject duplicates, response paths must not overwrite model/manifest exports, and uptake reporting must account for exchange coefficients. Passing adapter checks must not be presented as a correction of the unchanged upstream chemistry.

The saved [SYMBIONT reference simulation](../reports/reference-simulation.json) reports an optimal pFBA solution with biomass flux **0.22558277027184387 h⁻¹**, matching the declared numerical reference. Its maximum steady-state mass-balance residual is approximately `1.74e-14`, with zero bound violation. The pFBA total-flux objective is `481.3759339587058`; that quantity is not the growth rate. The built wheel was also installed into a separate directory and reproduced this reference using its bundled model/profile files. These are numerical reproduction checks under a synthetic, versioned profile, not measurements or calibrated process forecasts. The [synthetic replay](../reports/synthetic-replay.json) is a software demonstration, not a replay of private plant records.

The evidence supports using the separate repository for transparent model inspection, controlled coefficient experiments and explicitly qualified simulation. Quantitative biological conclusions still require review of the material chemistry/normalization findings and independent, held-out process measurements with a defensible biomass and substrate basis.
