# MEMOTE and responsible model changes

**iMcBath is the metabolic model; COBRApy and its solver calculate feasible fluxes; MEMOTE checks model quality.** MEMOTE is an open-source test suite for genome-scale metabolic models. It tests properties such as SBML validity, annotations, mass and charge balance, stoichiometric consistency, and biomass behavior. It can generate one-model snapshot reports, comparisons, and version-history reports. See the [official documentation](https://memote.readthedocs.io/en/latest/) and [MEMOTE paper](https://doi.org/10.1038/s41587-020-0446-y).

A MEMOTE score summarizes selected, weighted quality checks. It is not a probability of correctness, an estimate of prediction accuracy, or evidence that process parameters have been calibrated. Some diagnostics depend on modeling conventions. Read the individual failures and their explanations, not only the aggregate score. [Official report interpretation](https://memote.readthedocs.io/en/latest/understanding_reports.html).

## Two layers of coefficients

Keep metabolic-model changes distinct from the conversion of SYMBIONT process observations into model inputs.

| Layer | Examples | Meaning and verification |
| --- | --- | --- |
| Metabolic structure | Reaction stoichiometry, biomass composition, growth-associated ATP demand | These change the stoichiometric matrix or biomass definition. Check chemical balance, biomass units, energy consistency and the evidence for the change. |
| Metabolic constraints | Exchange bounds, reaction reversibility, maintenance bounds, objective weights | These change the feasible flux space or optimization goal. Record the scenario, units, assumptions and which constraints were changed. |
| Process conversion | Gas-volume reference basis, availability factors, liquid density, feed composition, inventory, dilution, optical-density calibration | These describe the reactor or its measurements. Keep them in the process/assumption configuration with provenance and calibration status. They must not silently rewrite metabolic stoichiometry. |

For example, a gas-controller setting in L/min is not a GEM uptake bound. Conversion requires a declared gas-volume basis, composition, culture volume, biomass basis and availability assumption. The resulting limit has units of mmol/(g modeled biomass·h). It describes a maximum possible uptake, not a measured consumption rate. Direct exchange-reaction fluxes and `model.medium` also use different sign conventions: COBRApy's medium dictionary takes positive import capacities. [COBRApy growth-media documentation](https://cobrapy.readthedocs.io/en/latest/media.html).

Standard flux balance analysis solves a steady-state intracellular balance, `S v = 0`, within reaction bounds. It does not infer gas transfer, inhibition, uptake kinetics, time evolution or measurement calibration by itself. SYMBIONT must supply those process relationships explicitly. Maintain a record of whether each input is measured, derived, assumed, or fitted, and retain a baseline before changing any parameter.

## Biomass normalization requires an audit

The inherited [`MCapsReport.html`](../MCapsReport.html) and root `index.html` contain a failed `test_biomass_consistency` diagnostic for `BIOMASS_Mcapsulatus`, reporting **0.9024111134789837** for the biomass component-mass calculation. This is an archived report value, not a newly measured conversion factor. Its result alone does not establish whether precursor definitions, chemical formulae, maintenance accounting, or biomass normalization require revision.

Do not multiply biomass, yields, or every biomass coefficient by `1/0.9024111134789837` as an automatic fix. Such a change alters the relationship between biomass flux, precursor demand and ATP demand. First audit the equation and the diagnostic under a recorded tool version, establish the intended biomass basis, and compare the proposed change with independent measurements. Preserve the original model and publish any correction as an explicit variant with its own tests.

The [iMcBath paper](https://doi.org/10.3389/fmicb.2018.02947) also states that maintenance requirements had not been measured for this organism: GAM was estimated and NGAM was borrowed from *E. coli*. Treat those as source-model assumptions. The published model's units should not be silently promoted to a validated dry-cell-weight calibration for SYMBIONT or another strain.

## Generate and interpret fresh evidence

Run from the repository root in the project's documented QA environment:

```sh
memote report snapshot --filename reports/memote.html ModelFiles/xml/iMcBath.xml
```

Create `reports/` first if necessary. The [official getting-started guide](https://memote.readthedocs.io/en/latest/getting_started.html) documents snapshot, diff and console-test modes. A useful run record includes the command, UTC timestamp, model SHA-256, MEMOTE/COBRApy/solver versions, exit status and report path. Check the report for failed, skipped and errored tests; successfully writing HTML is not equivalent to passing the suite. Exact results of newly executed runs belong in the corresponding run artifacts and repository validation summary.

For each proposed model variant, verify loading and solver status, feasible bounds and mass-balance residuals, expected behavior under declared reference conditions, and new MEMOTE failures relative to baseline. Biological validation additionally requires held-out observations with a defensible biomass calibration and substrate balances. A close endpoint biomass prediction alone cannot validate the trajectory, nutrient inventory, or a claimed limiting mechanism.

The historical upstream HTML reports and notebooks were inherited, not freshly reproduced by copying this repository. Use the model hashes in [UPSTREAM.md](UPSTREAM.md) to associate new evidence with the exact source model. Keep private process records outside public source control; this documentation records the integration principles without copying the underlying SYMBIONT source documents.
