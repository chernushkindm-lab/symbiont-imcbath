# LAB005 historical source audit

Inspected 1 October 2026. Findings apply to the exact local snapshots below; remote-link byte identity has not been assumed. Originals remain outside Git. Runtime manifests retain URI, modification/read times, cell locators and parser version.

## August schemas and coverage

| CSV suffix | Header rows | Columns | Physical rows | Interpretation |
|---|---:|---:|---:|---|
| Протоколы | 2 | 75 | 748 | 746 scheduled rows; 666 contain pH, temperature and RPM |
| Журнал наблюдений | 1 | 8 | 460 | Operator events; actions require interpretation |
| Пробы для аналитики | 2 | 35 | 2000 | 356 populated sample records |
| ПС | 3 | 65 | 1001 | 165 preparation batches |
| КПС | 2 | 51 | 843 | 28 concentrate batches |
| МЭ | 2 | 42 | 843 | 7 trace-stock batches |
| Титранты | 2 | 16 | 843 | Separate KOH and ammonia tables; 31 batches total |
| Перенос концентраций | 3 | 227 | 2001 | Undated derived worksheet; audit only |

Core coverage is **30 August 22:00 to 28 September 11:00, 2026, Asia/Yekaterinburg** (UTC: 30 August 17:00 to 28 September 06:00). Eighty scheduled rows lack all three core measurements; schedules do not extend observed coverage. Journal row 2 records inoculation at 30 August 21:33 local. The first process point is 0.45 h after time zero.

The exact import finds:

- 75 core rows with O2+CH4+CO2 above 100.2%; rejected without renormalization.
- 920 spreadsheet-error cells in mapped observed process rows.
- 110 negative source-derived delivery cells; never interpreted as negative physical delivery.
- 243 bottle mass increases requiring replacement/reset/noise interpretation.
- Raw working volume 7–12 L, alongside the separate authoritative 10 L.
- 18 duplicate observation identities, retained for review.
- 34,100 normalized observations, 356 samples, 231 batches and 648 event records.
- Zero known result-availability timestamps.

Conservative operator/bottle boundaries prevent unsupported interpolation; they are not validated biological phases. Process row 3 contains OD 0.427 and legacy ASV 1.1168 g/L. The authoritative coefficient instead gives **0.09508503349109931 g/L total dry residue**. Both remain traceable. This discrepancy does not independently validate either biomass estimate; OD 0.427 is outside the calibration range.

Methane column AJ is L/h; BU is a derived L/min duplicate. Air, concentrator flow, oxygen purity and calculated air-oxygen component remain distinct. A blank inlet is unknown, not zero. Soft-sensor exhaust remains an explicit scenario, not a measured flow or verified tracer.

## Analytical and preparation evidence

Rapid NH3/NH4 has 142 populated entries; phosphate has 110. Intervals and inequalities remain censored. The annotation 50-100(10) is excluded pending explanation. Bottle identifiers in OD cells remain rejected identifiers.

Instrumental populated counts: Cu 87, Zn 96, Fe 32, Mn 32. Colorimetric NH3/NH4 and phosphate are empty. Instrumental NH4, K, Na, Mg, Ca, Cl, NO2, SO4, NO3, formate, phosphate, Ni and Co are empty. Header presence does not establish coverage or detection limits. Analysis-date and storage-time columns are empty.

| Record | Raw date | Treatment |
|---|---|---|
| МЭ0 | 27.28.26 | Invalid month; unknown timestamp |
| NH22 | 20.06.26 | June 20 retained, outside run preparation window |
| NH23 | 21.09 | Missing year and clock; unknown timestamp |
| ПС0 | 30.08.26; no clock | Local date retained, unknown timestamp |

The transfer worksheet contains **96,597 formula-error cells** and no explicit time axis. It is registered as derived evidence with error counts and source examples, not a clean concentration time series. Stock references and bottle labels can be traced; use/connection times, density, purity/hydration and verified delivery remain necessary for nutrient balances.

## Calibration workbook

User-authoritative endpoint: total dry residue.

- Calibration!B4: k = 0.22268157726252769 g/(L OD), X = k × OD.
- Calibration!B22:B23: stated coefficient CI 0.20993938306355778–0.2354237714614976.
- Calibration!B24: RMSE 0.6886066995321699 g/L.
- Calibration!A9:M17: nine dishes, OD 8.78–56.57, five candidate date/OD groups. These are not known independent biological samples.
- The current-calculation sheet uses 10 L and exposes the old D-versus-Q alternative. The user resolved Flow Rate as D [h⁻¹]; steady-state and actual-flow validity remain separate questions.
- Telemetry_Productivity contains October/November 2025 and January/February/March–April 2026 runs, not May/August.

Cached workbook values are read without formula execution. The coefficient is not fitted to historical productivity. Reported residue intervals propagate only the coefficient CI and show RMSE separately; they are not full prediction intervals or biological-replicate uncertainty. Wavelength/path/dilution, instrument transfer, blank/washing and drying conditions remain relevant. Medium solids can contribute to total residue.

## May replay

May remains a separate run with 58-column/two-header-row protocols: 724 scheduled rows, 417 core rows and 307 rows without all core measurements. Coverage: **12 May 20:00 to 30 May 22:00 local**. First journal inoculation: **12 May 23:13 local**. Earlier process records remain pre-inoculation evidence with negative elapsed time.

May has 305 core rows with invalid gas sums, 232 mapped process spreadsheet errors, 50 negative source-derived delivery cells, 12,159 observations and 276 events. Raw volume spans 8–10 L. Excel time-date/subsecond artifacts are flagged. Availability remains unknown.

Preparation/separation/drying/drain sheets are inventoried but not promoted to verified delivery or harvest. The report's 1.16 mL/min methane label conflicts with the workbook L/min header. The 250 g/L versus 250 mg/L ammonium report discrepancy remains unresolved. Shift-report coverage ending 09:00 and microscopy through 15:00 remain separate windows.

## Snapshot checksums

CSV names have prefix Эксперимент_Ф10_27.08.2026 - .

| Source | SHA-256 |
|---|---|
| Журнал наблюдений.csv | 9575ec18afa0b57a4b75b4de46ff3a7a725d495b123708a8b58473b21da5ea2e |
| КПС.csv | a21ffb7fc6fc9f5c3a53feebe4150bd4cdc1fc1ce62fcbc847f0e485308024ec |
| МЭ.csv | d0661c2901b4a07bb982ea43fdf081ce09605541bcbe31e978e09ddae635464c |
| Перенос концентраций.csv | ef9a4cf93d6bab43fc824ac2d93175e61bda720c6da0f54da524fd257050ed2b |
| Пробы для аналитики.csv | 105e30f8da207521b0ba8524c04ece03e12bcc32038a8ca99a496bae90cee6d0 |
| Протоколы.csv | 2ed0e024de77969ac1db029e85085efacc919bcbbce0f8890657c53746014afa |
| ПС.csv | e27dfca11b107d718d09ee88998a7387a34709b1badee4766e0fc0b267208ebc |
| Титранты.csv | 7b83fa4b6d7a179a86cc9063a6ecc69fbaccc898f3048a8365a71a75211f8d54 |
| F10_OD_DCW_real_productivity_calibration.xlsx | 65ceafb0486f267cc3c228152e02db677d4a1c61deba25c6e49a982913385422 |
| Эксперимент_Ф10_12.05.26.xlsx | 76c7bd23e0cf0e93ea3ab375d9b930d6db4b3d062b018b8df8f7e064902a1f7e |

## Supported outputs and gates

Supported: source-linked scalar/interval observations, real coverage, event evidence, raw/derived distinctions, separate May/August replay.

Conditional: OD-to-residue reconstruction, soft-sensor exhaust, D×residue steady-state productivity, cross-run calibration and residue-to-model-biomass mapping.

Blocked as measured/qualified claims: cellular gas uptake without flow/basis evidence; cellular nutrient uptake without delivery/chemistry/inventory evidence; independent gravimetric validation from OD-derived labels; prospective forecast qualification without reporting availability. Issue records retain severity, affected outputs, evidence, interpretation and resolution state. Resolved user decisions do not erase raw conflicts.
