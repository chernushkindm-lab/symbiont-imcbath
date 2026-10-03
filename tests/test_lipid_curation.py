import pytest

from symbiont_imcbath.core import apply_profile, load_baseline, solve
from symbiont_imcbath.lipid_curation import (
    BIOMASS_MOLECULAR_DEMAND,
    FATTY_ACID_COUNTS,
    PSEUDO_SCALE,
    PSEUDO_SPECIES,
    REACTION_STOICHIOMETRY,
    curate_lipids,
)


@pytest.fixture(scope="module")
def curated():
    return curate_lipids(load_baseline())[0]


def test_mixture_is_normalized_without_changing_relative_counts(curated):
    assert sum(FATTY_ACID_COUNTS.values()) == PSEUDO_SCALE == 999
    reaction = curated.reactions.MC_Average_FattyAcid
    total = -sum(reaction.metabolites[curated.metabolites.get_by_id(mid)]
                 for mid in FATTY_ACID_COUNTS)
    assert total == pytest.approx(1.0, abs=1e-12)
    assert reaction.metabolites[curated.metabolites.mc_fattyacid_c] == pytest.approx(1 / 999)
    assert reaction.lower_bound == 0


def test_all_pseudo_species_have_reviewed_formula_and_charge(curated):
    for metabolite_id, (formula, charge) in PSEUDO_SPECIES.items():
        metabolite = curated.metabolites.get_by_id(metabolite_id)
        assert metabolite.formula == formula
        assert metabolite.charge == charge


def test_entire_curated_lipid_chain_is_element_and_charge_balanced(curated):
    for reaction_id in REACTION_STOICHIOMETRY:
        residual = curated.reactions.get_by_id(reaction_id).check_mass_balance()
        assert all(abs(value) < 1e-9 for value in residual.values()), (reaction_id, residual)


def test_final_pc_methylation_has_no_artificial_oxygen_or_water(curated):
    reaction = curated.reactions.PMETM2_MCi
    assert curated.metabolites.o2_c not in reaction.metabolites
    assert curated.metabolites.h2o_c not in reaction.metabolites
    assert reaction.metabolites[curated.metabolites.amet_c] == -1
    assert reaction.metabolites[curated.metabolites.ahcys_c] == 1


def test_biomass_preserves_molecular_phospholipid_demand(curated):
    biomass = curated.reactions.BIOMASS_Mcapsulatus
    for metabolite_id, molecular_demand in BIOMASS_MOLECULAR_DEMAND.items():
        coefficient = -biomass.metabolites[curated.metabolites.get_by_id(metabolite_id)]
        assert coefficient * PSEUDO_SCALE == pytest.approx(molecular_demand, abs=1e-12)


def test_baseline_is_not_mutated():
    baseline = load_baseline()
    before = baseline.metabolites.mc_fattyacid_c.charge
    curated, provenance = curate_lipids(baseline)
    assert baseline.metabolites.mc_fattyacid_c.charge == before == -1
    assert curated.metabolites.mc_fattyacid_c.charge == -999
    assert provenance["curations"][-1]["status"] == "reviewed_candidate"


def test_curated_reference_profile_remains_solvable(curated):
    configured, _ = apply_profile(curated, "symbiont-reference")
    result = solve(configured, method="pfba")
    assert result["status"] == "optimal"
    assert result["numerically_feasible"]
    assert result["growth_rate_h"] > 0
