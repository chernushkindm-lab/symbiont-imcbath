"""Balance and event tests independent of assumptions in the full GEM."""
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from symbiont_imcbath.replay import replay_document


def q(value, unit):
    return {"value": value, "unit": unit, "provenance": "synthetic", "source": "Unit-test fixture"}


def document(step=0.25, end=1.0):
    return {
        "schema_version": 1,
        "time_step": q(step, "h"),
        "gas_basis": {"molar_volume": q(22.414, "L/mol"), "reference_conditions": "dry gas, 0 C, 101.325 kPa"},
        "initial": {"time": q(0, "h"), "biomass": q(1, "g_model_biomass/L"),
                    "nitrogen": q(5, "mmol_N/L"), "volume": q(10, "L")},
        "intervals": [{"start": q(0, "h"), "end": q(end, "h"), "volume": q(10, "L"),
                       "gas_streams": [{"name": "mixed gas", "flow": q(1, "L/min"),
                                        "mole_fractions": {"ch4": q(0.25, "1"), "o2": q(0.25, "1")},
                                        "availability_fractions": {"ch4": q(0.8, "1"), "o2": q(0.5, "1")}}],
                       "liquid_feeds": [{"name": "medium", "flow": q(0.5, "L/h"),
                                         "nitrogen_concentration": q(10, "mmol_N/L")},
                                        {"name": "KOH", "flow": q(0.5, "L/h"),
                                         "nitrogen_concentration": q(0, "mmol_N/L")}]}],
        "boluses": [], "observations": [],
    }


def solver(mu=0.2, uptake=0.3, calls=None):
    def solve(model, *, method, uptake_caps):
        if calls is not None:
            calls.append(deepcopy(uptake_caps))
        qn = min(uptake, uptake_caps["EX_nh4_e"])
        return {"status": "optimal", "growth_rate_h": mu,
                "fluxes": {"EX_nh4_e": -qn}, "residuals": {"max_mass_balance": 0.0}}
    return solve


def bolus(time, amount):
    return {"time": q(time, "h"), "nitrogen_amount": q(amount, "mmol_N"),
            "label": "Synthetic event", "negligible_volume": True}


def test_actual_liquid_volume_and_gas_conversion():
    calls = []
    result = replay_document(document(), solve_fn=solver(calls=calls))
    assert result["status"] == "completed"
    assert result["nitrogen_source_audit"]["status"] == "not_performed"
    first = result["steps"][0]
    assert first["dilution_h_inv"] == pytest.approx((0.5 + 0.5) / 10)
    assert first["nitrogen_feed_mmol_N_h"] == 5
    assert calls[0]["EX_ch4_e"] == pytest.approx(0.8 * 0.25 * 1 * 60 * 1000 / (22.414 * 10 * 1))
    assert calls[0]["EX_o2_e"] == pytest.approx(0.5 * 0.25 * 1 * 60 * 1000 / (22.414 * 10 * 1))
    assert calls[0]["EX_nh4_e"] == pytest.approx((5 / 0.25 + 5 / 10 - 0.1 * 5) / 1)
    for state in result["states"]:
        assert abs(state["nitrogen_ledger"]["closure_error_mmol_N"]) < 1e-10
    ledger = result["states"][-1]["nitrogen_ledger"]
    assert ledger["continuous_feed_mmol_N"] == pytest.approx(5)


def test_boluses_applied_once_at_exact_times_and_conserve_nitrogen():
    doc = document()
    doc["intervals"][0]["liquid_feeds"] = []
    doc["boluses"] = [bolus(1, 3), bolus(0.3, 2), bolus(0, 1), bolus(0.3, 4)]
    result = replay_document(doc, solve_fn=solver(mu=0, uptake=0))
    assert len(result["bolus_events"]) == 4
    assert result["states"][-1]["nitrogen_mmol_N_L"] == pytest.approx(6)
    assert result["states"][-1]["nitrogen_ledger"]["bolus_mmol_N"] == 10
    assert any(step["end_h"] == 0.3 for step in result["steps"])
    before = next(state for state in result["states"] if state["time_h"] == 0.3 and state["kind"] == "step_end")
    assert before["nitrogen_mmol_N_L"] == pytest.approx(5.1)
    for state in result["states"]:
        assert abs(state["nitrogen_ledger"]["closure_error_mmol_N"]) < 1e-10


def test_bolus_not_available_in_preceding_step():
    doc = document()
    doc["initial"]["nitrogen"] = q(0, "mmol_N/L")
    doc["intervals"][0]["liquid_feeds"] = []
    doc["boluses"] = [bolus(0.5, 2)]
    calls = []
    result = replay_document(doc, solve_fn=solver(mu=0, uptake=100, calls=calls))
    assert calls[0]["EX_nh4_e"] == 0
    assert calls[1]["EX_nh4_e"] == 0
    assert calls[2]["EX_nh4_e"] == pytest.approx(0.2 / 0.25)
    assert result["states"][-1]["nitrogen_mmol_N_L"] == pytest.approx(0)
    assert result["states"][-1]["nitrogen_ledger"]["net_cellular_removal_mmol_N"] == pytest.approx(2)


def test_observations_cannot_change_states_or_solver_steps():
    doc = document()
    without = replay_document(doc, solve_fn=solver())
    doc["observations"] = [{"time": q(0.123, "h"), "biomass": q(9999, "g_model_biomass/L")},
                           {"time": q(1, "h"), "nitrogen": q(0, "mmol_N/L")}]
    with_observations = replay_document(doc, solve_fn=solver())
    assert without["states"] == with_observations["states"]
    assert without["steps"] == with_observations["steps"]
    assert len(with_observations["observation_comparisons"]) == 2
    assert with_observations["observation_comparisons"][0]["residual_biomass"] < -9000


def test_step_halving_reduces_euler_error_against_known_growth_solution():
    # Constant mu and D make X(t) analytic; this tests the dynamic integrator,
    # independently of optimization degeneracy or biological parameter choices.
    coarse = replay_document(document(step=0.25, end=2), solve_fn=solver(mu=0.3, uptake=0))
    fine = replay_document(document(step=0.125, end=2), solve_fn=solver(mu=0.3, uptake=0))
    exact_x = math.exp((0.3 - 0.1) * 2)
    error_coarse = abs(coarse["states"][-1]["biomass_g_model_L"] - exact_x)
    error_fine = abs(fine["states"][-1]["biomass_g_model_L"] - exact_x)
    assert error_fine < 0.55 * error_coarse


def test_nitrogen_starvation_caps_uptake_without_negative_clamping():
    doc = document()
    doc["initial"]["nitrogen"] = q(0.01, "mmol_N/L")
    doc["intervals"][0]["liquid_feeds"] = []
    result = replay_document(doc, solve_fn=solver(mu=0, uptake=100))
    assert result["states"][-1]["nitrogen_mmol_N_L"] == pytest.approx(0)
    assert result["states"][-1]["nitrogen_ledger"]["net_cellular_removal_mmol_N"] == pytest.approx(0.1)
    assert result["states"][-1]["nitrogen_ledger"]["roundoff_adjustment_mmol_N"] <= 1e-10


def test_infeasible_solver_stops_before_any_state_update():
    doc = document()
    doc["observations"] = [{"time": q(1, "h"), "biomass": q(1, "g_model_biomass/L")}]
    result = replay_document(doc, solve_fn=lambda *a, **kw: {"status": "infeasible"})
    assert result["status"] == "stopped"
    assert result["solver_status"] == "infeasible"
    assert result["stopped_at_time_h"] == 0
    assert result["steps"] == []
    assert len(result["states"]) == 1
    assert result["observation_comparisons"][0]["status"] == "outside_completed_window"


def test_numerically_invalid_solver_stops_before_state_update():
    result = replay_document(document(), solve_fn=lambda *a, **kw: {"status": "optimal", "numerically_feasible": False})
    assert result["status"] == "stopped"
    assert result["steps"] == []
    assert "numerical mass-balance" in result["reason"]


@pytest.mark.parametrize("change, match", [
    (lambda d: d["initial"]["biomass"].update(value=0), "positive"),
    (lambda d: d["initial"]["nitrogen"].update(value=-1), "nonnegative"),
    (lambda d: d["time_step"].update(value=float("nan")), "finite"),
    (lambda d: d["time_step"].update(value=float("inf")), "finite"),
    (lambda d: d["time_step"].update(value=True), "finite"),
    (lambda d: d["initial"]["nitrogen"].update(unit="mg_NH4/L"), "expected unit"),
    (lambda d: d["initial"]["volume"].update(provenance="unknown"), "provenance"),
    (lambda d: d["initial"]["volume"].update(provenance=[]), "provenance"),
    (lambda d: d["initial"]["volume"].pop("source"), "missing fields"),
    (lambda d: d["intervals"][0]["start"].update(value=0.2), "contiguous"),
    (lambda d: d["intervals"][0]["volume"].update(value=8), "variable-volume"),
    (lambda d: d["intervals"][0]["end"].update(value=0), "greater"),
    (lambda d: d["intervals"][0]["gas_streams"][0]["mole_fractions"]["o2"].update(value=0.9), "exceed one"),
    (lambda d: d["intervals"][0]["gas_streams"][0]["availability_fractions"]["ch4"].update(value=1.1), "at most"),
    (lambda d: d["intervals"][0]["liquid_feeds"][0]["flow"].update(value=-1), "nonnegative"),
    (lambda d: d.update(boluses=[bolus(2, 1)]), "within the replay window"),
    (lambda d: d.update(boluses=[{**bolus(0.5, 1), "negligible_volume": False}]), "negligible_volume"),
    (lambda d: d.update(unknown_coefficient=1), "unknown fields"),
])
def test_invalid_input_rejected_before_solve(change, match):
    doc = document()
    change(doc)
    calls = []
    with pytest.raises(ValueError, match=match):
        replay_document(doc, solve_fn=solver(calls=calls))
    assert calls == []


def test_large_dilution_automatically_splits_for_positive_euler_state():
    doc = document(step=1)
    doc["intervals"][0]["liquid_feeds"][0]["flow"] = q(30, "L/h")
    result = replay_document(doc, solve_fn=solver(mu=0, uptake=0))
    assert result["status"] == "completed"
    assert all(step["step_h"] * step["dilution_h_inv"] <= 0.5 + 1e-12 for step in result["steps"])
    assert all(state["nitrogen_mmol_N_L"] >= 0 and state["biomass_g_model_L"] > 0 for state in result["states"])


def test_material_negative_nitrogen_is_reported_not_silently_clamped():
    doc = document(step=1)
    doc["initial"]["nitrogen"] = q(0, "mmol_N/L")
    doc["intervals"][0]["liquid_feeds"] = []
    def slightly_violating_solver(model, *, method, uptake_caps):
        return {"status": "optimal", "growth_rate_h": 0, "fluxes": {"EX_nh4_e": -1e-8}}
    result = replay_document(doc, solve_fn=slightly_violating_solver)
    assert result["status"] == "stopped"
    assert "negative nitrogen" in result["reason"]
    assert result["states"][-1]["nitrogen_mmol_N_L"] == 0


def test_synthetic_example_runs_on_actual_imcbath_with_step_halving():
    from symbiont_imcbath.core import apply_profile, load_baseline
    path = Path(__file__).resolve().parents[1] / "examples" / "replay-input.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    model, _ = apply_profile(load_baseline(), "symbiont-reference")
    coarse = replay_document(doc, model=model)
    doc["time_step"]["value"] /= 2
    fine = replay_document(doc, model=model)
    assert coarse["status"] == fine["status"] == "completed"
    assert coarse["states"][-1]["time_h"] == fine["states"][-1]["time_h"] == 1
    difference = abs(coarse["states"][-1]["biomass_g_model_L"] - fine["states"][-1]["biomass_g_model_L"])
    assert difference < 0.005  # Numerical sensitivity for this small synthetic case only.
    for result in (coarse, fine):
        assert all(abs(state["nitrogen_ledger"]["closure_error_mmol_N"]) < 1e-8 for state in result["states"])
        assert all(state["nitrogen_mmol_N_L"] >= 0 for state in result["states"])
        assert result["states"][-1]["nitrogen_ledger"]["bolus_mmol_N"] == 2
        assert result["model_provenance"]["baseline_sha256"]
        assert result["nitrogen_source_audit"]["status"] == "passed"
        audited = {entry["reaction_id"]: entry for entry in result["nitrogen_source_audit"]["boundary_details"]}
        assert audited["SK_cyan_c"]["kind"] == "other_boundary"
        assert audited["EX_no3_e"]["kind"] == "exchange"
        assert audited["SK_cyan_c"]["lower_bound"] == 0


def test_default_upstream_model_is_rejected_before_nitrogen_free_growth():
    doc = document()
    doc["initial"]["nitrogen"] = q(0, "mmol_N/L")
    doc["intervals"][0]["liquid_feeds"] = []
    with pytest.raises(ValueError, match="EX_no3_e.*explicit ammonium-only"):
        replay_document(doc)


def test_ammonium_only_reference_cannot_grow_without_declared_nitrogen():
    from symbiont_imcbath.core import apply_profile, load_baseline
    model, _ = apply_profile(load_baseline(), "symbiont-reference")
    doc = document(end=0.25)
    doc["initial"]["nitrogen"] = q(0, "mmol_N/L")
    doc["intervals"][0]["liquid_feeds"] = []
    result = replay_document(doc, model=model)
    assert result["status"] == "completed"
    assert result["nitrogen_source_audit"]["status"] == "passed"
    assert result["states"][-1]["biomass_g_model_L"] == pytest.approx(1, abs=1e-9)
    assert result["states"][-1]["nitrogen_mmol_N_L"] == pytest.approx(0, abs=1e-9)
    assert abs(result["steps"][0]["growth_rate_h_inv"]) < 1e-9


@pytest.mark.parametrize("source", ["EX_no3_e", "EX_urea_e", "EX_asp__L_e", "SK_cyan_c"])
def test_custom_profile_cannot_open_an_untracked_nitrogen_source(source):
    from symbiont_imcbath.core import apply_profile, load_baseline
    reference, _ = apply_profile(load_baseline(), "symbiont-reference")
    custom, _ = apply_profile(reference, {
        "schema_version": 1, "id": "test-alternative-nitrogen",
        "provenance": {"source": "Regression fixture", "status": "synthetic_assumption"},
        "reaction_bounds": {source: {"lower_bound": -1, "upper_bound": 1000}},
    })
    calls = []
    with pytest.raises(ValueError, match=source):
        replay_document(document(), model=custom, solve_fn=solver(calls=calls))
    assert calls == []
    assert custom.reactions.get_by_id(source).lower_bound == -1  # Reject without mutating the caller.


def test_noncanonical_nh3_exchange_orientation_is_checked_for_import():
    from cobra import Metabolite, Reaction
    from symbiont_imcbath.core import apply_profile, load_baseline
    model, _ = apply_profile(load_baseline(), "symbiont-reference")
    nh3 = Metabolite("nh3_test_e", formula="H3N", compartment="e")
    exchange = Reaction("EX_nh3_test_e")
    exchange.add_metabolites({nh3: 1})  # Positive flux supplies the N-containing metabolite.
    exchange.bounds = (0, 1)
    model.add_reactions([exchange])
    calls = []
    with pytest.raises(ValueError, match="EX_nh3_test_e"):
        replay_document(document(), model=model, solve_fn=solver(calls=calls))
    assert calls == []
    exchange.bounds = (-1, 0)  # Export-only orientation is admissible.
    result = replay_document(document(), model=model, solve_fn=solver())
    assert result["nitrogen_source_audit"]["status"] == "passed"


def test_modified_ammonium_exchange_cannot_invalidate_atom_ledger():
    from symbiont_imcbath.core import apply_profile, load_baseline
    model, _ = apply_profile(load_baseline(), "symbiont-reference")
    exchange = model.reactions.get_by_id("EX_nh4_e")
    exchange.add_metabolites({model.metabolites.get_by_id("nh4_e"): -1})
    with pytest.raises(ValueError, match="one N atom per flux unit"):
        replay_document(document(), model=model, solve_fn=solver())
