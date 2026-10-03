# Reviewed lipid curation: 999-equivalent pseudo-units

Status: **reviewed candidate**. The immutable upstream iMcBath model remains unchanged.

## Scope

This curation treats the lipid representation as one coupled system. It covers the
fatty-acid mixture, average fatty acid, activated fatty-acyl-CoA, glycerophospholipid
intermediates, PE/PG/cardiolipin/PC branches, and the corresponding biomass terms.

The affected pseudo-species are:

`mc_fattyacid_c`, `mc_fattyacidcoa_c`, `1agpgafa_MC_c`, `pa_MC_c`,
`cdpdag_MC_c`, `pgp_MC_c`, `pg_MC_c`, `clpn_MC_c`, `ps_MC_c`,
`pe_MC_c`, `pme_MC_c`, `pdme_MC_c`, and `pc_MC_c`.

Every reaction incident on these species is curated:
`MC_Average_FattyAcid`, `MC_AFAA`, `G3PAT_MCi`, `APG3PAT_MCi`,
`PHCYT_MCi`, `PGSA_MCi`, `PGPP_MCi`, `CLPNS_MC`, `PSSA_MCi`,
`PSD_MCi`, `PETOHM_MCi`, `PMETM_MCi`, `PMETM2_MCi`, plus the four
phospholipid coefficients in `BIOMASS_Mcapsulatus`.

## Source mixture and normalization

Notebook 4 encoded the following fatty-acid fractions for the average pool,
citing UniBio, Bird et al. (1971), and Müller et al. (2004):

| Fatty acid | Model metabolite | Upstream fraction | Reviewed fraction |
| --- | --- | ---: | ---: |
| C14:0 | `ttdca_c` | 0.061 | 61/999 |
| C14:1 | `ttdcea_c` | 0.007 | 7/999 |
| C15:0 | `ptdca_c` | 0.010 | 10/999 |
| C16:0 | `hdca_c` | 0.729 | 729/999 |
| C17:0 | `hpdca_c` | 0.089 | 89/999 |
| cyclopropane C17:0 | `cpoa2h_c` | 0.092 | 92/999 |
| C18:0 | `ocdca_c` | 0.004 | 4/999 |
| C18:1 | `ocdcea_c` | 0.007 | 7/999 |
| **Total** | | **0.999** | **1.000** |

The correction does **not** invent a missing 0.001 fatty-acid species. It treats
the eight published values as rounded relative counts and normalizes their
existing ratios. This is deliberately conservative: published work supports a
C16:0/C16:1-dominated membrane in *M. capsulatus*, while temperature and oxygen
can alter unsaturation/isomer and cyclopropane abundance. A future
condition-specific lipid composition should therefore be a separate model
profile supported by measurements, not silently substituted here.

## Pseudo-unit convention

The original correction notebook calculated the aggregate elemental sum
`C16041H31055O1998`, but then treated it as a 1000-molecule pseudo-species.
The underlying counts total 999. The reviewed convention is:

> **one pseudo-unit = an aggregate of 999 normalized molecular equivalents**

A one-molecule-equivalent biochemical reaction therefore uses a pseudo-species
coefficient of `1/999`. This keeps SBML chemical formulas and charges integral
without changing the intended molecular scale of the reactions.

| Pseudo-species | Reviewed aggregate formula | Charge |
| --- | --- | ---: |
| `mc_fattyacid_c` | C16041H31055O1998 | -999 |
| `mc_fattyacidcoa_c` | C37020H62024N6993O16983P2997S999 | -3996 |
| `1agpgafa_MC_c` | C19038H37049O6993P999 | -1998 |
| `pa_MC_c` | C35079H67105O7992P999 | -1998 |
| `cdpdag_MC_c` | C44070H79093N2997O14985P1998 | -1998 |
| `pgp_MC_c` | C38076H73099O12987P1998 | -2997 |
| `pg_MC_c` | C38076H74098O9990P999 | -999 |
| `clpn_MC_c` | C73155H140204O16983P1998 | -1998 |
| `ps_MC_c` | C38076H73099N999O9990P999 | -999 |
| `pe_MC_c` | C37077H74098N999O7992P999 | 0 |
| `pme_MC_c` | C38076H76096N999O7992P999 | 0 |
| `pdme_MC_c` | C39075H78094N999O7992P999 | 0 |
| `pc_MC_c` | C40074H80092N999O7992P999 | 0 |

These formulas and charges are propagated sequentially by exact elemental and
charge conservation using the baseline model's protonation convention. The
curation test requires every affected reaction to balance to numerical tolerance.

## Reaction corrections

All pseudo coefficients formerly represented as 0.001 are replaced by 1/999
molecular-equivalent coefficients. The average-mixture coefficients are
normalized to count/999. `MC_Average_FattyAcid` is made irreversible so the
bookkeeping pool cannot act as an artificial source of its individual fatty acids.

The final PC methylation also contained a separate encoded chemistry defect.
`PMETM2_MCi` is annotated as KEGG R01320 / EC 2.1.1.71, but the upstream model
consumes 1.5 O2 and produces 3 H2O. The reviewed reaction is the SAM-dependent
methyl transfer:

`SAM + (1/999) PDME -> SAH + H+ + (1/999) PC`

No oxygen or water term is used.

## Biomass contribution

The molecular phospholipid demands are preserved from the original biomass
construction; only the aggregate-unit divisor changes from 1000 to 999:

| Biomass component | Molecular demand | Reviewed pseudo coefficient |
| --- | ---: | ---: |
| PC | 0.00937385 | 0.00937385 / 999 |
| PE | 0.09134262 | 0.09134262 / 999 |
| cardiolipin | 0.00315904 | 0.00315904 / 999 |
| PG | 0.01538077 | 0.01538077 / 999 |

Using standard atomic weights, these four phospholipid terms contribute
approximately 0.08565 g per nominal biomass unit. This curation does **not**
renormalize the full biomass reaction; the separate ~0.9024 biomass-mass finding
must be reassessed after this lipid correction.

The free-fatty-acid biomass terms are not replaced by the pseudo-pool. They
represent the separately retained non-phospholipid fatty-acid fraction in the
published reconstruction and remain unchanged in this curation.

## Acceptance gates

The candidate is acceptable for further validation only if:

1. all affected reactions pass element and charge balance;
2. the eight normalized mixture fractions sum to one;
3. the four biomass terms preserve their original molecular demand;
4. the immutable upstream model remains byte-identical;
5. the SYMBIONT reference profile remains solver-feasible;
6. fresh MEMOTE chemistry results no longer report the lipid mass/charge defects;
7. growth, methane, oxygen and nitrogen predictions are compared before/after;
8. the full biomass mass ledger is recalculated before claiming a 1 gDCW basis.

Implementation: `src/symbiont_imcbath/lipid_curation.py`.
Tests: `tests/test_lipid_curation.py`.
