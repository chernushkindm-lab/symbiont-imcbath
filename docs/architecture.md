# M10 evidence and deployment architecture

## Actual starting point

The private repository was cloned from chernushkindm-lab/symbiont-imcbath at 417fa2bb331eec7a2b49350eb10b3604369b55fd on 2026-10-01. This supersedes the prompt's older f3ab4c6 review snapshot. The current repository already has a Python adapter, constant-volume synthetic replay, pinned model artifacts, tests, modern dependency declarations, profiles and a MEMOTE failure review. No AGENTS.md was found. No original model or laboratory source was executed or altered.

Development branch: codex/m10-historical-service. M10 adds historical ingestion and a local authenticated scientific service; it reuses symbiont_imcbath.core for metabolic solves. The inherited replay is a regression component, not proof of historical performance.

## Module boundary

~~~mermaid
flowchart LR
 A["M01–M03\nimmutable originals / normalization / events"] --> B["M04–M08\ninventory functions + evidence quality"]
 B --> C["M09\nvalidity and information cutoff"]
 C --> D["M10\nconditional iMcBath capacity"]
 C --> E["Independent kinetics\npure coupled ODE"]
 D --> F["M13\nmatched evaluation / abstention"]
 E --> F
 F --> G["M14\nlocal chart + report"]
 A --> G
 G --> H["M15–M16\ncompeting hypotheses / researcher review"]
 I["M17\nhashes + model audit + run manifests"] --> C
 J["M18\nhealth / job failure / data age"] --> G
~~~

These names describe minimal integration interfaces. This release does not claim all eighteen SYMBIONT modules exist. No control command is sent to a device. An external Go host may use the versioned HTTP API; no duplicate balance engine is introduced.

## Confirmed decisions

- LAB005, FA10, F10/Ф10 and YFC-10L refer to the same reactor.
- Acquisition timezone is Asia/Yekaterinburg, UTC+05:00.
- August is the implementation case; May remains a separate comparison.
- 10 L is the user-authoritative volume scenario. Original 7–12 L entries remain evidence and conflicts are not overwritten.
- The output endpoint is total dry residue. It is not automatically cellular DCW or GEM-normalized producer biomass.
- Displayed Flow Rate is dilution D in h^-1. D×X is a steady-state proxy, not generally transient formation.
- DO is percent air saturation; solubility/pressure and calibration conditions still require evidence.
- The last nonempty notebook variant supplies structure only. Demonstration parameters remain uncalibrated.
- Standalone Python with a versioned Go boundary, local computer only. No public or remote deployment is authorized.

Versioned machine-readable decisions are in m10/config/decisions.json.

## Physical and computational separation

Observation-window reconstruction can use retrospective source joins only with explicit labels. The forecast path requires availability timestamps no later than the forecast origin and separately frozen preprocessing/calibration. Missing reporting timestamps do not become measurement timestamps. The historical source cannot currently qualify prospective forecasts.

Gas channels summing above tolerance are invalid; missing inlets are not zero. Inlet-only exhaust has an identifiability deficit. The soft-sensor implementation supports explicit closure scenarios and uncertainty bounds, but does not create a measured gas balance. A model-derived uptake used as a GEM input cannot independently validate that same model.

Net residue inventory change can be calculated for matched, same-segment observations with explicit volume assumptions. Cellular production and nutrient assimilation need additional evidence. Conditional GEM capacity at the observed state is not a free-running biomass forecast. Independent kinetic and GEM tracks remain separate; no ensemble is enabled without held-out benefit.

## Service architecture

FastAPI serves one authenticated browser application and a versioned /api/v1 interface. Each scientific job uses a child process, one active job per service, a 180-second timeout, cancellation and one BLAS thread. Uploaded CSV is parsed as data only. Upload byte/row/column limits and explicit field mappings apply. Imported rows preserve censoring, raw content, failed values, IDs, hashes and QC.

Run directories are isolated by validated identifiers. Original bytes are stored by SHA-256. Export manifests include original and model hashes, source commit, code hashes, configuration hash and exact scientific package versions. Historical run hashes cover sources, code and decisions. Changing any of them invalidates a cached result; output timestamps are provenance and are not part of numerical equivalence.

Authentication uses a local random access key and eight-hour HTTP-only SameSite=Strict sessions. The key never appears in URLs. Nonlocal origins cannot mutate state. Hostnames are restricted. Data, schema, exports, image previews and application assets require authentication. Only /healthz and the sign-in form are anonymous. Secrets/private evidence are ignored by Git. Native launch binds 127.0.0.1; Compose publishes 127.0.0.1 only. This is a single-user local deployment, not a multi-tenant production host.

Native Windows jobs do not enforce hard memory limits. Supplied Docker limits CPU, RAM and process count; container execution is a separate verification step. A service restart interrupts running jobs. Completed job metadata and private logs persist; restart does not silently resume work.

## Deliverable qualification

| Output | Qualification |
|---|---|
| Source manifest and exact snapshot QC | Supported by imported bytes and row locators |
| Observation plots, source events, microscopy previews | Supported; sample links and uncertainty remain explicit |
| OD-derived total dry residue | Conditional on source calibration/instrument applicability |
| Interval residue accumulation | Conditional on endpoint and volume; not gross cellular formation |
| D×X proxy | Conditional steady-state interpretation |
| Gas uptake and nutrient assimilation | Blocked where exhaust/chemistry/inventory evidence is insufficient |
| GEM numerical regression / conservation checks | Software/model checks; not VS1 experimental validation |
| Historical GEM capacity | Explicit scenario only |
| Independent kinetic implementation | Tested reference cases; historical parameters uncalibrated |
| Paired forecast scores / ensemble | Withheld until information and independent target requirements hold |
| Local browser/API deployment | Requires live service, job, export and access-control checks |
| Container deployment | Configuration provided; requires Docker host verification |

## Completion and rollback

Use m10/README.md for commands, storage configuration and local access. Existing upstream notices remain intact. Reproducible numerical and API tests are separate from the fresh MEMOTE audit and from experimental qualification. Keep inherited model quality findings visible. Roll back code/environment while retaining private originals and versioned run outputs; migrate evidence through explicit schema-versioned exports rather than overwriting originals.
