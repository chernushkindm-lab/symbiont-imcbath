from copy import deepcopy
import pytest
from m10.metabocore.gem import FLUX_UNIT, capacity, model_audit_summary, reference_regression


def request():
    return {"schema_version": 1, "run_id": "regression-fixture", "window_id": "synthetic",
            "mode": "capacity", "uptake_bounds": {
                r: {"lower": 0, "upper": v, "unit": FLUX_UNIT,
                    "provenance": "assumed", "source": "profiles/symbiont-reference.json", "parent_observation_ids": []}
                for r, v in (("EX_ch4_e", 16), ("EX_o2_e", 28), ("EX_nh4_e", 2.3))}}


def test_model_reference_and_pinned_integrity():
    assert model_audit_summary()["model_integrity"] == "verified"
    result = reference_regression()
    assert result["regression_passed"]
    assert result["growth_rate_h"] == pytest.approx(0.2255827702718434, abs=1e-9)
    assert result["pfba_total_flux"] > 100
    assert result["growth_rate_h"] != result["pfba_total_flux"]


def test_capacity_preserves_request_and_requires_residue_mapping_for_productivity():
    data = request()
    original = deepcopy(data)
    result = capacity(data)
    assert data == original
    assert result["status"] == "conditional"
    assert result["mu_capacity_h"] == pytest.approx(0.2255827702718434, abs=1e-9)
    assert result["gross_capacity_g_model_L_h"] is None
    assert result["gross_capacity_status"] == "blocked_missing_biomass_mapping"
    assert {r["reaction_id"] for r in result["open_carbon_nitrogen_sources"]} == {"EX_ch4_e", "EX_nh4_e"}
    assert result["active_exchange_bounds"]["EX_nh4_e"] == [-2.3, 0]


def test_mapping_is_explicit_and_does_not_relabel_dry_residue():
    data = request()
    data["biomass"] = {"value": 8, "unit": "g_dry_residue/L", "source": "synthetic fixture"}
    data["biomass_mapping"] = {"factor_g_model_per_g_residue": 0.5, "source": "declared scenario", "status": "assumed"}
    result = capacity(data)
    assert result["gross_capacity_g_model_L_h"] == pytest.approx(result["mu_capacity_h"] * 4)
    assert result["experimental_validation"] == "not_qualified"
    assert result["biomass_observation"]["unit"] == "g_dry_residue/L"


def test_reconciliation_abstains_from_assumed_uptake():
    data = request()
    data["mode"] = "reconciliation"
    result = capacity(data)
    assert result["status"] == "blocked"
    assert result["solver_status"] == "not_run"
    assert result["mu_capacity_h"] is None


def test_missing_supply_is_not_implicitly_unlimited():
    data = request()
    del data["uptake_bounds"]["EX_nh4_e"]
    result = capacity(data)
    assert result["status"] == "blocked"
    assert "EX_nh4_e" in result["reasons"][0]


@pytest.mark.parametrize("bad", [-1, float("inf"), float("nan"), True, "16"])
def test_bad_flux_caps_rejected(bad):
    data = request()
    data["uptake_bounds"]["EX_ch4_e"]["upper"] = bad
    with pytest.raises(ValueError):
        capacity(data)


def test_concentration_cannot_be_used_as_flux():
    data = request()
    data["uptake_bounds"]["EX_nh4_e"]["unit"] = "mmol/L"
    with pytest.raises(ValueError, match="concentration is not a flux"):
        capacity(data)


def test_starvation_infeasible_does_not_become_zero_growth():
    data = request()
    data["uptake_bounds"]["EX_ch4_e"]["upper"] = 0
    result = capacity(data)
    assert result["status"] == "blocked"
    assert result["solver_status"] == "infeasible"
    assert result["mu_capacity_h"] is None
    assert result["gross_capacity_g_model_L_h"] is None


def test_fva_and_finite_sensitivity_preserve_meaning():
    data = request()
    data["fva_reactions"] = ["EX_ch4_e", "EX_co2_e"]
    data["sensitivity_fraction"] = 0.01
    result = capacity(data)
    assert result["fva"]["statistical_interval"] is False
    assert result["fva"]["reactions"]["EX_ch4_e"]["minimum"] < 0
    assert result["finite_perturbation_sensitivity"]["reactions"]["EX_nh4_e"]["mu_change_h"] > 0


def test_valid_zero_growth_is_distinct_from_failure():
    data = request()
    data["uptake_bounds"]["EX_nh4_e"]["upper"] = 0
    result = capacity(data)
    assert result["status"] == "conditional"
    assert result["solver_status"] == "optimal"
    assert result["mu_capacity_h"] == pytest.approx(0, abs=1e-9)


def test_reconciliation_uses_explicit_intervals_and_parent_lineage():
    data = request()
    data["mode"] = "reconciliation"
    data["biomass_mapping"] = {"factor_g_model_per_g_residue": 1, "source": "synthetic validated-mapping fixture", "status": "validated"}
    for bound in data["uptake_bounds"].values():
        bound["provenance"] = "recalculated"
        bound["parent_observation_ids"] = ["synthetic-observation-fixture"]
    result = capacity(data)
    assert result["status"] == "conditional"
    assert result["solver_status"] == "optimal"
    assert result["forecast_qualification"] == "not_qualified"


def test_memote_unicode_loader_retries_same_bytes_and_removes_temporary_copy(tmp_path, monkeypatch):
    from scripts import run_memote
    monkeypatch.setattr(run_memote.platform, "system", lambda: "Windows")
    source = tmp_path / "model-\u03bc.xml"
    source.write_bytes(b"immutable model fixture")
    attempts = []

    class FakeAPI:
        @staticmethod
        def validate_model(path):
            from pathlib import Path
            p = Path(path)
            attempts.append(p)
            assert p.read_bytes() == source.read_bytes()
            if len(attempts) == 1:
                return None, None, {"errors": ["File unreadable."], "warnings": []}
            assert str(p).isascii()
            return "loaded-fixture", (3, 1, 2), {"errors": [], "warnings": []}

    model, _, notifications, diagnostic = run_memote.validate_portable(FakeAPI, source)
    assert model == "loaded-fixture"
    assert notifications["errors"] == []
    assert diagnostic["ascii_copy_used"]
    assert not attempts[1].exists()
    assert source.read_bytes() == b"immutable model fixture"


def test_memote_does_not_retry_scientific_validation_errors(tmp_path, monkeypatch):
    from scripts import run_memote
    monkeypatch.setattr(run_memote.platform, "system", lambda: "Windows")
    source = tmp_path / "model-\u03bc.xml"
    source.write_bytes(b"invalid fixture")
    attempts = []

    class FakeAPI:
        @staticmethod
        def validate_model(path):
            attempts.append(path)
            return None, None, {"errors": ["Malformed XML element"], "warnings": []}

    _, _, _, diagnostic = run_memote.validate_portable(FakeAPI, source)
    assert len(attempts) == 1
    assert not diagnostic["ascii_copy_used"]
