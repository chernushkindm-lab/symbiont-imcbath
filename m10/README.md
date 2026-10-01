# M10 MetaboCore local historical service

Adds traceable LAB005 ingestion, QC, conditional model calls, an independent kinetic reference implementation and a private browser workflow to the existing iMcBath adapter. A validated VS1 forecast is not established.

From the repository root, in isolated Python 3.12:

~~~powershell
python -m pip install -r m10/requirements-lock.txt
python -m pip install --no-deps -e .
$env:PYTHONPATH = "$PWD\m10;$PWD\src"
$env:M10_SOURCE_DIR = (Split-Path $PWD -Parent)
python -m metabocore.worker --run August
python -m metabocore.worker --run May
python -m uvicorn metabocore.api:app --host 127.0.0.1 --port 8050 --no-access-log
~~~

Open http://127.0.0.1:8050. The generated access key is in m10/private/access-token.txt. Alternatively set M10_ACCESS_TOKEN to a private random string of at least 24 characters. Never put the key in a URL. Page, API, schema, images and exports require authentication; /healthz reveals only health. Sessions expire after eight hours. This release is one local user / one local process. Network access is not authorized.

The project is a Google Drive mount. A local-disk scientific environment installs much faster than one within that mount. Change private run storage using M10_DATA_DIR; OS and existing Drive permissions govern direct file access.

The browser provides run selection, source-linked chart cursors, QC/event/observation inspection, model status, microscopy references, CSV normalization preview, mappings and exports. Only UTF-8 CSV uploads are accepted. Notebooks/macros/scripts never execute. Originals and mappings persist under content-addressed import folders. A new run ID avoids overwriting prior imports.

One scientific child process runs at a time, with a 180-second deadline, cancellation and one BLAS thread. Docker adds memory/CPU/PID limits. Hard memory limits are not enforced by the native Windows launcher. Terminal metadata/logs persist privately; restart interrupts running jobs and does not imply completion.

~~~powershell
python -m pytest tests m10/tests
python scripts/audit_m10_model.py
python scripts/run_memote.py --output reports/m10-audit
~~~

The CI workflow keeps the original adapter and MEMOTE jobs and adds M10 tests using the locked dependencies and synthetic fixtures. It does not require private historical data. The local fresh MEMOTE path above is the path read by the service audit panel. The model-format helper returns exit code 1 for the retained YAML divergence; JSON/SBML are the verified runtime/audit pair. MEMOTE also returns exit code 1 for its inherited model findings.

Docker Compose binds only loopback. Container configuration must be built/tested on a Docker host before claiming container deployment. The authenticated API schema is at /api/v1/openapi.json. Go can call this versioned API without duplicating numerical balances.

Exports: normalized CSV, Parquet retaining nested evidence as record JSON, result JSON, manifest, SVG/PNG chart, evaluation CSV and HTML report. Private originals, images, results and keys are ignored by Git. Missing forecasts produce an explicit not-scored evaluation row.

Rollback: stop the service, retain M10_DATA_DIR, restore prior code/environment. Schema version 1 is append-only. Export and import to a new run ID for migration. Back up private storage before upgrades. Originals are checked by SHA-256 on replay.

## Local release verification

The current implementation and scientific qualification are recorded in [the validation report](../docs/validation_report.md). On this computer, `./m10/start-local.ps1` uses the private runtime record to select the installed local scientific environment. Pass `-Python` to select another installed environment.

Run `python scripts/verify_m10_service.py --historical` against the running loopback service to exercise its actual workers, both historical imports, exports and verified cache reuse. It reads the key from private storage or the environment and prints job status only. `scripts/verify_m10_browser.cjs` verifies sign-in, chart inspection, CSV normalization, job execution, exports and a researcher review using explicitly synthetic records; it requires Playwright and an installed Microsoft Edge browser. Verification artifacts stay under private/verification.

Hypothesis reviews remain separate from causal claims. Each accepted-as-working, rejected or deferred review needs a reason and retains the reviewed run hash. Previous decisions remain in the append-only history when a reconstruction changes; they are not automatically reapplied to new evidence.
