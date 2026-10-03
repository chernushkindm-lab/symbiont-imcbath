"""Reviewed lipid pseudo-unit curation for iMcBath.

The immutable upstream model is never modified. This module creates a derivative
model with one coherent 999-molecule aggregate convention for the measured
average fatty-acid mixture and every dependent phospholipid pseudo-species.
"""
from __future__ import annotations

import copy
from fractions import Fraction

import cobra

LIPID_CURATION_ID = "lipid-pseudounit-999-v1"
PSEUDO_SCALE = 999

# Counts behind the published iMcBath mixture. The upstream decimal fractions
# sum to 0.999 because these integer counts were divided by 1000.
FATTY_ACID_COUNTS = {
    "ttdca_c": 61,       # C14:0
    "ttdcea_c": 7,       # C14:1
    "ptdca_c": 10,       # C15:0
    "hdca_c": 729,       # C16:0
    "hpdca_c": 89,       # C17:0
    "cpoa2h_c": 92,      # cyclopropane C17:0
    "ocdca_c": 4,        # C18:0
    "ocdcea_c": 7,       # C18:1
}
assert sum(FATTY_ACID_COUNTS.values()) == PSEUDO_SCALE

# Each formula/charge describes an aggregate of 999 molecular equivalents.
# Values were derived by exact elemental/charge conservation through the
# reaction chain below, using the baseline model's protonation convention.
PSEUDO_SPECIES = {
    "mc_fattyacid_c": ("C16041H31055O1998", -999),
    "mc_fattyacidcoa_c": ("C37020H62024N6993O16983P2997S999", -3996),
    "1agpgafa_MC_c": ("C19038H37049O6993P999", -1998),
    "pa_MC_c": ("C35079H67105O7992P999", -1998),
    "cdpdag_MC_c": ("C44070H79093N2997O14985P1998", -1998),
    "pgp_MC_c": ("C38076H73099O12987P1998", -2997),
    "pg_MC_c": ("C38076H74098O9990P999", -999),
    "clpn_MC_c": ("C73155H140204O16983P1998", -1998),
    "ps_MC_c": ("C38076H73099N999O9990P999", -999),
    "pe_MC_c": ("C37077H74098N999O7992P999", 0),
    "pme_MC_c": ("C38076H76096N999O7992P999", 0),
    "pdme_MC_c": ("C39075H78094N999O7992P999", 0),
    "pc_MC_c": ("C40074H80092N999O7992P999", 0),
}

U = 1.0 / PSEUDO_SCALE

# Absolute coefficients. Negative = reactant, positive = product.
REACTION_STOICHIOMETRY = {
    "MC_Average_FattyAcid": {
        **{mid: -count / PSEUDO_SCALE for mid, count in FATTY_ACID_COUNTS.items()},
        "mc_fattyacid_c": U,
    },
    "MC_AFAA": {
        "atp_c": -1, "coa_c": -1, "mc_fattyacid_c": -U,
        "amp_c": 1, "ppi_c": 1, "mc_fattyacidcoa_c": U,
    },
    "G3PAT_MCi": {
        "glyc1p_c": -1, "mc_fattyacidcoa_c": -U,
        "1agpgafa_MC_c": U, "coa_c": 1,
    },
    "APG3PAT_MCi": {
        "1agpgafa_MC_c": -U, "mc_fattyacidcoa_c": -U,
        "coa_c": 1, "pa_MC_c": U,
    },
    "PHCYT_MCi": {
        "ctp_c": -1, "h_c": -1, "pa_MC_c": -U,
        "cdpdag_MC_c": U, "ppi_c": 1,
    },
    "PGSA_MCi": {
        "cdpdag_MC_c": -U, "glyc1p_c": -1,
        "cmp_c": 1, "h_c": 1, "pgp_MC_c": U,
    },
    "PGPP_MCi": {
        "h2o_c": -1, "pgp_MC_c": -U, "pg_MC_c": U, "pi_c": 1,
    },
    "CLPNS_MC": {
        "pg_MC_c": -2 * U, "clpn_MC_c": U, "glyc_c": 1,
    },
    "PSSA_MCi": {
        "cdpdag_MC_c": -U, "ser__L_c": -1,
        "cmp_c": 1, "h_c": 1, "ps_MC_c": U,
    },
    "PSD_MCi": {
        "h_c": -1, "ps_MC_c": -U, "co2_c": 1, "pe_MC_c": U,
    },
    "PETOHM_MCi": {
        "amet_c": -1, "pe_MC_c": -U,
        "ahcys_c": 1, "h_c": 1, "pme_MC_c": U,
    },
    "PMETM_MCi": {
        "amet_c": -1, "pme_MC_c": -U,
        "ahcys_c": 1, "h_c": 1, "pdme_MC_c": U,
    },
    # KEGG R01320 / EC 2.1.1.71: no O2 consumption or H2O production.
    "PMETM2_MCi": {
        "amet_c": -1, "pdme_MC_c": -U,
        "ahcys_c": 1, "h_c": 1, "pc_MC_c": U,
        "o2_c": 0, "h2o_c": 0,
    },
}

# Original molecular phospholipid demands before the upstream /1000 aggregate
# conversion. Dividing by 999 preserves the same molecular biomass demand.
BIOMASS_MOLECULAR_DEMAND = {
    "pc_MC_c": 0.00937385,
    "pe_MC_c": 0.09134262,
    "clpn_MC_c": 0.00315904,
    "pg_MC_c": 0.01538077,
}


def _set_absolute(reaction: cobra.Reaction, coefficients: dict[str, float]) -> None:
    for metabolite_id, coefficient in coefficients.items():
        metabolite = reaction.model.metabolites.get_by_id(metabolite_id)
        reaction.add_metabolites({metabolite: float(coefficient)}, combine=False)


def curate_lipids(model: cobra.Model) -> tuple[cobra.Model, dict]:
    """Return a derivative with the reviewed lipid representation applied."""
    curated = model.copy()
    changes = []

    for metabolite_id, (formula, charge) in PSEUDO_SPECIES.items():
        metabolite = curated.metabolites.get_by_id(metabolite_id)
        before = {"formula": metabolite.formula, "charge": metabolite.charge}
        metabolite.formula = formula
        metabolite.charge = charge
        changes.append({"kind": "lipid_species", "metabolite_id": metabolite_id,
                        "before": before, "after": {"formula": formula, "charge": charge}})

    for reaction_id, coefficients in REACTION_STOICHIOMETRY.items():
        reaction = curated.reactions.get_by_id(reaction_id)
        before = {m.id: float(c) for m, c in reaction.metabolites.items()}
        _set_absolute(reaction, coefficients)
        if reaction_id == "MC_Average_FattyAcid":
            reaction.bounds = (0.0, reaction.upper_bound)
        after = {m.id: float(c) for m, c in reaction.metabolites.items()}
        changes.append({"kind": "lipid_reaction", "reaction_id": reaction_id,
                        "before": before, "after": after})

    biomass = curated.reactions.get_by_id("BIOMASS_Mcapsulatus")
    before_biomass = {mid: float(biomass.metabolites[curated.metabolites.get_by_id(mid)])
                      for mid in BIOMASS_MOLECULAR_DEMAND}
    for metabolite_id, molecular_demand in BIOMASS_MOLECULAR_DEMAND.items():
        biomass.add_metabolites(
            {curated.metabolites.get_by_id(metabolite_id): -molecular_demand / PSEUDO_SCALE},
            combine=False,
        )
    after_biomass = {mid: float(biomass.metabolites[curated.metabolites.get_by_id(mid)])
                     for mid in BIOMASS_MOLECULAR_DEMAND}
    changes.append({"kind": "biomass_lipid_units", "reaction_id": biomass.id,
                    "before": before_biomass, "after": after_biomass})

    record = {
        "id": LIPID_CURATION_ID,
        "status": "reviewed_candidate",
        "pseudo_scale": PSEUDO_SCALE,
        "mixture_counts": copy.deepcopy(FATTY_ACID_COUNTS),
        "mixture_fractions": {k: str(Fraction(v, PSEUDO_SCALE))
                              for k, v in FATTY_ACID_COUNTS.items()},
        "changes": changes,
        "assumptions": [
            "The eight published iMcBath fatty-acid proportions are treated as rounded counts totaling 999 and normalized without changing their relative ratios.",
            "All averaged lipid species use one aggregate of 999 molecular equivalents so SBML formulas and charges remain integral.",
            "The molecular phospholipid demand in biomass is preserved; only the aggregate-unit divisor changes from 1000 to 999.",
            "PMETM2_MCi follows the annotated SAM-dependent methyl-transfer chemistry and does not consume O2 or produce H2O.",
        ],
    }
    history = copy.deepcopy(getattr(model, "_symbiont_provenance",
                                    {"status": "untracked_model", "curations": [], "assumptions": []}))
    history.setdefault("curations", []).append(record)
    history.setdefault("assumptions", []).extend(record["assumptions"])
    curated._symbiont_provenance = history
    return curated, copy.deepcopy(history)
