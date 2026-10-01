# M10 validation and scientific release status

Report date: **2 October 2026**. This is a historical evidence and conditional-model release. **It is not a calibrated or qualified LAB005 forecasting release.** Software and the local authenticated workflow passed the checks below; scientific qualification remains separate.

## Release checks

| Check | Verified evidence | Release interpretation |
|---|---|---|
| Final complete software suite | **205 passed, 2 skipped**, 38.08 s; skips concern unavailable Windows symbolic-link creation; three dependency deprecation warnings | Adapter and M10 implementation checks passed. See `reports/generated/m10-all-tests.xml`, private `all-tests.log` and [committed verification summary](../reports/m10-release/verification-summary.json). |
| Fresh MEMOTE audit | **147 cases: 80 failed, 59 passed, 8 skipped, 0 JUnit errors; score 54.05%; exit 1** | Completed **with model findings**, not a clean audit pass. Executed 1 October 21:37:40–21:41:37 UTC; [audit metadata](../reports/m10-audit/run-metadata.json), [JUnit](../reports/m10-audit/junit.xml), [interpretation](model_audit.md). |
| Model artifact identity | Pinned original hashes retained. JSON and SBML functionally agree; YAML is a different historical model state | Runtime JSON and audit SBML are the selected consistent pair. YAML is not interchangeable. [Integrity evidence](../reports/m10-audit/model-integrity.json). |
| GEM reference regression | Biomass flux **0.22558277027184387 h⁻¹**, within fixed 10⁻⁹ tolerance | Numerical reproduction, not LAB005 experimental validation. [Reference result](../reports/m10-audit/reference-regression.json). |
| Independent kinetic branch | Pure coupled ODE, events, nonnegative states and conservation tested; synthetic carbon residual **1.42×10⁻¹³ g**, tolerance 10⁻⁸ g | Numerical implementation verified. Notebook parameters are not fitted to historical observations. |
| Historical predictive evaluation | **0 paired forecast scores; 0 baseline predictions** in both saved runs | Intentionally not scored: reporting availability is unknown. No claimed forecast accuracy or ensemble benefit. |
| Local deployment | **20 browser checks passed, zero JavaScript errors**; six real service jobs checked model audit, kinetic conservation, August/May reconstruction and verified cache reuse; eight export formats downloaded for each historical run | Loopback authenticated page, API, images/schema and exports tested. Upload → normalization/QC → job → chart/export and persistent synthetic-fixture review passed. Docker configuration is supplied but **not built/tested**; no remote/public deployment. |

The fresh MEMOTE findings are separate from Windows launch/path and interrupted multiprocessing diagnostics. The completed audit used one process and retained its assertions and tolerances. Neither its weighted score nor the software test count measures forecasting accuracy.

## Historical coverage and calculations

These figures were read from private `runs/LAB005-2026-08/result.json` and `runs/LAB005-2026-05/result.json`, with their manifests. Both runs were regenerated through the live service with verified immutable input sets and the completed model audit. Their manifests retain the exact reconstruction time, source commit, code/model/input hashes and export checksums. The source coverage and algebraic summaries below are verified.

| Evidence / result | August | May, kept separate |
|---|---:|---:|
| Scheduled protocol rows / rows with pH, temperature and RPM | 746 / **666** | 724 / **417** |
| Observed local coverage, UTC+05 | 30 Aug 22:00–28 Sep 11:00 | 12 May 20:00–30 May 22:00 |
| Normalized observations | 34,100 | 12,159 |
| Source events / conservative segments | 648 / 232 | 276 / 64 |
| OD-derived total-residue points | 664 | 412 |
| Within-segment residue inventory intervals | 449 | 359 |
| Exact-time conditional D×residue proxies | 616 | 360 |
| Legacy ASV comparisons | 664 | 397 |
| Invalid gas triplets, sum >100.2% | 75 | 305 |
| Negative inferred-delivery cells | 110 | 50 |
| Spreadsheet-error cells in observed records | 920 | 232 |
| Residue values excluded from baseline forecasting for unknown availability | 664 | 412 |

August inoculation time is 30 August **21:33 UTC+05**, from the journal; the first protocol observation is later at 22:00. May retains two core records before its first recorded inoculation. Segment counts describe conservative event boundaries, not experimentally established biological phases.

At the user-authoritative 10 L, interval calculations use Δ(VX)/Δt, maximum interval 4 h, and source-linked endpoints within the same segment/calibration. They measure change in **estimated total-residue inventory**, not gross cellular formation. Exact-time D×residue maxima are **2.3956** and **2.4465 g/(L h)** for August and May. These are conditional dilution proxies based on source-derived D; they are not measured harvest productivity and do not establish or refute the May report's 3 g/(L h) claim. The legacy/selected-residue ratio spans **0.9971–11.7453** and **1.0247–47.3254**, respectively: disagreement between derived channels, not independent validation error.

Source trace example: August protocol **AP3/AP4**, observations `obs-a5f1c52894ae821a54128082` and `obs-e3ff54bb04ab5959a133a0f4`, calibration `F10-total-dry-residue-65ceafb0486f`. Exact hashes, source roles and cell references remain in the private manifests and [source audit](source_audit.md). Calibration-coefficient intervals do not include all OD, sample, volume or transfer uncertainty; shared calibration errors are not independent endpoint errors.

## Conditional capacity and confirmed decisions

The saved August example uses protocol row **119**, **4 September 13:00 UTC**. Its GEM result is conditional capacity: **μ=0.280676 h⁻¹** and **0.631263 g modeled biomass/(L h)** at the supplied state. It assumes dry inlet gas at 25 °C/1 atm, pure methane, 100% inlet supply availability, an illustrative modeled-biomass/residue factor of 1, and the reference NH4 cap 2.3 mmol/(g modeled biomass h). It uses reported concentrator purity; sMMO, ATPM and permissive mineral settings remain disclosed scenario choices. It does not infer measured cellular uptake, mass transfer, VS1 equivalence or a free-running forecast. Infeasible/missing-input calculations remain blocked rather than becoming zero growth.

Decisions version **2026-10-02.1** confirms shared reactor aliases, Asia/Yekaterinburg acquisition time, authoritative 10 L with raw-volume conflicts retained, total dry residue as the endpoint, Flow Rate as **D [h⁻¹]**, DO as **percent air saturation**, and the last notebook variant's structure only. The user also confirmed that a blank air cell accompanying recorded concentrator operation means air was off; zero is used only in that source-linked scenario, while the original blank remains. Other missing inlets are not zero. Forecast horizons 1/4/12 h remain provisional. Standalone Python with a Go adapter boundary and **local-computer-only** deployment are authorized. [Versioned decisions](../m10/config/decisions.json).

## Blockers and exact missing evidence

| Output still blocked or conditional | Missing input / unresolved finding |
|---|---|
| Prospective baseline, kinetic or GEM scoring | Verified result/reporting availability, frozen preprocessing/calibration, comparable independent held-out outcomes and known-versus-assumed future controls. Event times cannot substitute for availability. |
| Cellular growth / GEM-to-residue comparison | Independent residue method/instrument applicability and a validated cellular/producer/model-biomass observation mapping. Nine calibration dishes are not nine demonstrated biological replicates. |
| Measured exhaust, MUR/OUR/CER/RQ | Independent exhaust closure or justified conserved tracer, gas basis/calibration/delay, meter conditions and inventories. Inlet-only flow is not identifiable without additional assumptions. |
| Actual liquid delivery and net formation | Bottle connection/reset events, density/calibration, verified delivery and withdrawal/sample/harvest/addition quantities. Recorded 7–12 L conflicts remain visible despite the 10 L decision. |
| Cellular N/P/Cu/Fe uptake | Dated recipe-to-use links, chemical/density/purity basis, matched inventory assays and nonbiological sinks. August has 140 accepted rapid NH3/NH4 and 110 rapid PO4 records, including censoring; instrumental nutrient columns are largely empty. |
| Historical kinetic calibration / transfer | Conditions-matched solubility and broth transfer evidence, initial states and identifiable parameter set. DO's percent reference alone does not determine mg/L; chemical sulfite kLa tests are not a broth curve. |
| Culture composition attribution | Ten local microscopy images exist, but sample/time links are unverified. Morphotype counts are not species identities or biomass fractions. |
| May interpretation | Methane L/min versus report mL/min; ammonium mg/L versus g/L; separate report/microscopy windows; support sheets inventoried rather than verified delivery/harvest. |

## Scope and partial features

The release provides source-preserving normalization/QC, interval balance functions, conditional GEM solving, an independent kinetic numerical reference, local charts/exports, and evidence-linked diagnostic hypotheses. Eight hypothesis alternatives are a **review sequence**, not a causal ranking; confidence remains unresolved, and morphology has no linked run evidence. Counts describe matching records, not independent corroborations. Both historical records now retain eight evidence-linked alternatives. Researcher reviews are stored separately as append-only, version-linked decisions; an old review remains history and is not automatically accepted for changed evidence.

Historical nutrient assimilation, independently calibrated kinetics, historical dynamic GEM forecasting, learned ensemble fusion and automatic causal diagnosis are not completed features. Existing dynamic GEM replay is an integration boundary, not a validated historical forecast. CSV upload performs mapping/QC; unspecified matrix/basis or unverified units do not become scientific validation. The Go boundary is an adapter interface, not integration with an existing Go host. Native Windows jobs have no hard memory cap; container configuration is not proof of a tested container deployment.

These limitations are deliberate qualification boundaries or remaining scope, not evidence of predictive success. Supporting details: [scientific assumptions](scientific_assumptions.md), [data contract](data_contract.md), [architecture](architecture.md), and [model audit](model_audit.md).
