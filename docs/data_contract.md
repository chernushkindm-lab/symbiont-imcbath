# M10 evidence contract v1

Implementation: m10/metabocore/contracts.py and m10/metabocore/ingestion.py.
Schema: m10.evidence/1.0. Parser: lab005.historical/1.0.0.

## Entities and identifiers

Run, segment, sample, observation, equipment, calibration, preparation batch, delivery interval, event, model release, scenario, forecast and hypothesis are separate typed entities. Dataclasses and observation_schema() provide a portable JSON contract; they do not imply every adjacent SYMBIONT module exists.

Historical run IDs LAB005-2026-08 and LAB005-2026-05 share EQ-BR-001. User-confirmed aliases: LAB005, FA10, F10, Ф10 and YFC-10L. Source IDs derive from exact-byte SHA-256. Observation IDs derive from source ID, sheet, physical row, column and parameter. Repeated imports preserve IDs; changed snapshots create new IDs. Catalogue keys are not sample identities.

Observations contain raw value/unit, normalized value/unit, basis, matrix, classification, parameter, run/segment/sample IDs, equipment/sensor IDs, calibration version, source locator, QC flags, acceptance/exclusion state, uncertainty/censoring and parent IDs. Recalculations add an equation version. Forecast/imputation fields cannot be replaced by a classification label.

Measured, source-derived, recalculated, imputed, assumed/synthetic, predicted and setpoint remain distinct. Pump commands are setpoints. Spreadsheet ASV, gas/nutrient uptake and inferred bottle-flow columns remain source-derived. New OD-to-residue values are recalculated with the FEK OD observation as parent. FEK, raw µCheck, converted µCheck and independent gravimetry remain separate.

The user chose total dry residue [g/L]. It is not cellular DCW or model biomass without an explicit scenario mapping. Raw volume is retained separately from the authoritative 10 L. Flow Rate means dilution D [h⁻¹], per user confirmation. D×X still requires steady-state and representative nonselective outflow. DO means percent air saturation; calibration conditions remain unverified.

## Time and availability

Store UTC event_time, original local_time and Asia/Yekaterinburg (UTC+05:00). Filename dates never establish process start. File mtime, upload time, preparation time and import read time never substitute for analytical availability.

Date carry is bounded to the same explicit protocol day and 23 subsequent hourly rows. Backward clock movement without a new date, invalid dates, missing clocks or blank blocks cannot invent tomorrow's date. Excel serial dates are supported. Time-date artifacts are flagged. Fractional-second serial errors within 50 ms of a whole second are rounded and flagged; original raw cells remain unchanged.

Date-only preparation records retain their local date and null timestamp. NH22's June date remains June with a conflict flag; NH23's incomplete date and МЭ0's invalid month remain unresolved.

Historical result availability is unknown. available_at() rejects unknown/future reporting times, event-after-availability inconsistencies and stale values. This blocks prospective qualification of this snapshot. Event-time retrospective replay remains available and must be labeled accordingly.

## Units and censoring

Matrices distinguish broth, medium, water, gas, titrant, concentrate and trace stock. Salt/species concentration is not elemental concentration, free-ion activity or cellular flux. NH3/NH4 combined rapid assays retain their unresolved species basis; phosphate remains PO4. Preparation date is not connection time.

Numeric parsing accepts decimal commas and Unicode minus. Spreadsheet errors, nonfinite values, misplaced bottle identifiers and unexplained annotations retain raw values and rejection reasons. Ranges retain bounds with null point values. Less-than assays are left-censored; greater-than and plus-suffixed assays are right-censored. Missing and below detection are never converted to zero. A literal zero remains source-entered evidence subject to method QC.

Normalized CSV uploads require mappings for event time, parameter, value, unit, classification, basis and matrix. Times require offsets. Known parameter codes require expected units. Recalculated/imputed/predicted uploads require the full JSON lineage contract, not a CSV label alone. The importer returns a mapping preview.

## Identity, segments and computation gates

Operator inoculation, drain/refill, stopping/failure and bottle-label changes create conservative interpolation boundaries. Journal categories do not automatically prove a biological event; event text, source locator and review state remain available. A bottle-label change records an interval from the last old label to the first new label, not an exact connection time. Preparation stock references are independent.

Duplicate identities are retained and require review. Gas fractions are not renormalized. O2+CH4+CO2 above the source-review threshold of 100.2% is rejected. Valid fractions alone do not qualify a gas balance: exhaust flow/tracer, inlet purity, basis, conditions and delay remain separate gates. August methane L/h is primary; its derived L/min duplicate is not an extra stream.

## APIs and storage

- import_august(source_dir, calibration_path=None, read_time=None): experiment-data directory, workspace root or protocols path with sibling CSVs.
- import_may(workbook_path, calibration_path=None, read_time=None): separate May run.
- parse_normalized_csv(data, mapping, run_id=..., source_name=...): strict upload preview.

Outputs include run ID, sources, observations, samples, batches, events, segments, series, coverage, issues, mapping preview, decisions and output support status. Series rows expose UTC/local time, elapsed hours, source row, QC flags and observation IDs. Series are a display index, not a replacement for evidence.

Manifests preserve filename, source URI, SHA-256, bytes, source modification/read times, acquisition time (null if unknown), run coverage, parser version, role and access status. Cell locators preserve physical row numbering including multilevel headers. Protected artifact storage must preserve immutable originals. CSV/Parquet exports must retain raw values, classification and lineage. Reimport selects a new snapshot rather than modifying prior evidence.

Numeric content and IDs are deterministic. A fixed read_time reproduces the entire import object, including audit metadata. The importer never executes source notebooks or formulas.

## Researcher hypothesis reviews

Authenticated `GET /api/v1/runs/{run_id}/hypothesis-reviews` returns `{run_id, run_hash, reviews, latest}`. `reviews` contains the complete append-only history in revision order; `latest` maps hypothesis IDs to their latest review only when the stored run hash equals the current run hash and the hypothesis still exists. A regenerated run therefore retains its prior review history without inheriting an earlier decision as current.

Authenticated `POST` on the same endpoint accepts `hypothesis_id`, `status` (`accepted_as_working`, `rejected` or `deferred`), a required nonblank `reason` of 1–2000 characters, and optional `evidence_ids` (at most 100 IDs of 1–200 characters). The hypothesis must exist in the current run; each evidence ID must identify a current-run observation or source. Duplicate evidence IDs are retained once in their original order. Unsupported fields are rejected. A successful POST returns the saved review object with HTTP 201.

The server adds a unique `review_id`, `run_id`, increasing per-run `revision`, UTC `reviewed_at` and the current `run_hash`. Entries are appended and flushed to `private/reviews/{run_id}.jsonl`; earlier entries and scientific run artifacts are unchanged. Corrupt or incomplete logs reject further appends without truncation. Revision assignment is serialized within the supported single-process local service. Authentication establishes access to this shared local workspace, not a named researcher identity.

A review is an explicit researcher decision, not a new measurement, causal proof, model recalibration or automatic experiment approval. An acceptance marks a working hypothesis only. No review is generated automatically; review timestamps do not become analytical information-availability timestamps.
