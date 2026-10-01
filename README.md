# SYMBIONT iMcBath

An independent implementation of Christian Lieven's **iMcBath** genome-scale
metabolic model for *Methylococcus capsulatus* (Bath), with editable coefficients
and a Python/JSON interface for SYMBIONT. The published name is iMcBath.

The original model has **913 reactions, 879 compartment-specific metabolites and
730 genes**. Its JSON, SBML and YAML files, supporting data and Git history are
retained. Source: [ChristianLieven/memote-m-capsulatus](https://github.com/ChristianLieven/memote-m-capsulatus),
commit `f3ab4c6bf5d78d8c2f0daeaf40e843fe458c8160`;
[Lieven et al., 2018](https://doi.org/10.3389/fmicb.2018.02947).

## Install and run

Use Python 3.11 or 3.12; Python 3.12 is the tested runtime. From this repository:

~~~bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[test,qa]"
python -m symbiont_imcbath info
python -m symbiont_imcbath simulate --profile symbiont-reference --method pfba
python -m pytest
~~~

The reference profile reproduces **mu = 0.2255827702718434 h^-1**, using sMMO,
ATPM fixed at 8.39 and methane/oxygen/ammonium uptake caps of 16/28/2.3
mmol/(g modeled biomass h). These are declared architecture assumptions, not
fitted operating recommendations. No coefficient is silently adjusted to match
observations.

## Inspect and change coefficients

~~~bash
python -m symbiont_imcbath inspect BIOMASS_Mcapsulatus
python -m symbiont_imcbath inspect ATPM
python -m symbiont_imcbath validate-profile examples/custom-profile.json
python -m symbiont_imcbath simulate --profile symbiont-reference --profile examples/custom-profile.json
python -m symbiont_imcbath export reports/generated/edited-model.xml --profile symbiont-reference --profile examples/custom-profile.json
~~~

Copy the custom example and give it a meaningful version ID/source. Profiles
support reaction bounds, objective coefficients and absolute stoichiometric
replacements. Zero removes a metabolite from a reaction. Edits apply to fresh
model copies and carry a before/after audit trail. The pinned files are
hash-checked and protected from export overwrite. Exports include a provenance
manifest. See [COEFFICIENTS.md](docs/COEFFICIENTS.md).

**Bounds and stoichiometry do different jobs.** A negative exchange lower bound
limits uptake; it is a rate, not concentration or a gas-controller setting.
Stoichiometric coefficients describe reaction chemistry or biomass composition.
Changes can break mass/charge balance and require a fresh model audit.

## Integrate with SYMBIONT

~~~python
from symbiont_imcbath.core import load_baseline, apply_profile, solve

model, provenance = apply_profile(load_baseline(), "symbiont-reference")
result = solve(model, method="pfba", uptake_caps={
    "EX_ch4_e": 16.0, "EX_o2_e": 28.0, "EX_nh4_e": 2.3,
})
if result["status"] == "optimal" and result["numerically_feasible"]:
    mu = result["growth_rate_h"]
~~~

The CLI returns JSON and exit codes 0 (success), 2 (invalid input), or 3
(infeasible/stopped). Failed solves return null predictions. Results record
model/profile provenance, software versions and residuals. pFBA growth is the
biomass reaction flux; its total-flux objective is reported separately.

~~~bash
python -m symbiont_imcbath replay examples/replay-input.json --profile symbiont-reference --output reports/generated/replay.json
~~~

The dynamic adapter uses explicit units and measured/derived/synthetic
provenance, gas capacities, actual liquid flow and volume, a nitrogen inventory
ledger, exact-time boluses and withheld observations. It supports controlled
constant volume and requires an ammonium-only nitrogen intake profile.
Dynamic gas/N capacities replace the three static uptake bounds; they are not
additional physiological ceilings.

The example is synthetic. The supplied
[SYMBIONT reference](https://docs.google.com/document/d/1XspPz6hL60vsEdvUsfcxWHRTwvjkGATJo9AOZxDgyDg/edit)
guided the contract; its historical workbook/package and live system were not
integrated. Its 72-hour results are not claimed as reproduced here.
[SYMBIONT.md](docs/SYMBIONT.md) defines the schema, workbook mapping,
nitrogen-basis rules and limitations.

## Quality and evidence

**MEMOTE is a quality test suite, not a growth prediction service.** It checks
structural consistency, annotations, balances and other model properties.
FBA/pFBA gives conditional flux predictions. Experimental validation is a
separate comparison against measurements.

~~~bash
python scripts/run_memote.py
~~~

This writes HTML, JSON, JUnit and model-hash/run metadata under
reports/generated/ and preserves the audit exit code. Inherited findings remain
visible; no arbitrary coefficient changes are made to suppress them.
GitHub Actions runs adapter tests and the audit and stores private artifacts.
No report is published to GitHub Pages.

See [VALIDATION.md](docs/VALIDATION.md) for fresh results,
[MEMOTE.md](docs/MEMOTE.md) for interpretation and
[UPSTREAM.md](docs/UPSTREAM.md) for attribution/hashes. Original reports,
Results/, notebooks and scripts are inherited evidence, not new executions.
The original README is docs/UPSTREAM_README.md; obsolete Travis configuration
is in legacy/.

Published biomass normalization is preserved. The archived approximate 0.902
mass diagnostic is not used as a correction multiplier. Quantitative biological
release still needs normalization, cycle, phenotype, medium and held-out
process validation.

## License and dependencies

The upstream ISC license and Christian Lieven's notice are retained in LICENSE
and bundled model data. New adapter code uses the same license. Cite the original
model paper, and [MEMOTE, 2020](https://doi.org/10.1038/s41587-020-0446-y) when using
its methodology. Direct dependency pins are in pyproject.toml;
requirements-lock.txt records the tested environment.
