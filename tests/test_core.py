import copy
import hashlib
import json

import cobra
import pytest

from symbiont_imcbath.core import (
    BASELINE_COUNTS, BASELINE_SHA256, BIOMASS_ID, ProfileError,
    apply_profile, baseline_path, export_model, inspect_reaction, load_baseline,
    load_profile, model_info, solve,
)


def editable_profile(**changes):
    return {
        "schema_version": 1, "id": "test-edit",
        "provenance": {"source": "test fixture", "status": "synthetic_assumption"},
        "assumptions": ["Computational test only"], **changes,
    }


@pytest.fixture(scope="module")
def baseline():
    return load_baseline()


@pytest.fixture(scope="module")
def reference(baseline):
    return apply_profile(baseline, "symbiont-reference")[0]


def test_exact_pinned_baseline_and_fresh_instances(baseline):
    assert hashlib.sha256(baseline_path().read_bytes()).hexdigest() == BASELINE_SHA256
    assert model_info(baseline)["counts"] == BASELINE_COUNTS
    second = load_baseline()
    second.reactions.EX_ch4_e.lower_bound = -1
    assert baseline.reactions.EX_ch4_e.lower_bound == -18.46
    assert model_info(baseline)["objective"]["coefficients"] == {BIOMASS_ID: 1.0}


def test_tampered_baseline_rejected(tmp_path):
    altered = tmp_path / "altered.json"
    altered.write_bytes(baseline_path().read_bytes() + b"\n")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_baseline(altered)


def test_upstream_profile_is_unchanged(baseline):
    configured, provenance = apply_profile(baseline, "upstream-baseline")
    assert cobra.io.to_json(configured) == cobra.io.to_json(baseline)
    assert provenance["profiles"][-1]["changes"] == []


def test_reference_growth_fba_and_pfba(reference):
    for method in ("fba", "pfba"):
        result = solve(reference, method=method)
        assert result["status"] == "optimal"
        assert result["growth_rate_h"] == pytest.approx(0.2255827703, abs=1e-8)
        assert result["growth_rate_h"] == result["fluxes"][BIOMASS_ID]
        assert result["objective_value"] == pytest.approx(result["growth_rate_h"])
        assert result["numerically_feasible"]
        assert result["residuals"]["max_mass_balance"] < 1e-7
        assert result["residuals"]["max_bound_violation"] < 1e-7
        if method == "pfba":
            assert result["pfba_total_flux"] > result["growth_rate_h"] * 100


def test_absolute_coefficients_and_objective_do_not_mutate(baseline):
    original = inspect_reaction(baseline, BIOMASS_ID)["metabolites"]["atp_c"]
    profile = editable_profile(
        stoichiometry={BIOMASS_ID: {"atp_c": -25.0, "2ddg6p_c": 0}},
        reaction_bounds={"ATPM": {"lower_bound": 5.0, "upper_bound": 5.0}},
        objective={"direction": "max", "coefficients": {BIOMASS_ID: 2.0}},
    )
    patched, provenance = apply_profile(baseline, profile)
    assert inspect_reaction(patched, BIOMASS_ID)["metabolites"]["atp_c"] == -25.0
    assert "2ddg6p_c" not in inspect_reaction(patched, BIOMASS_ID)["metabolites"]
    assert inspect_reaction(baseline, BIOMASS_ID)["metabolites"]["atp_c"] == original
    assert baseline.reactions.ATPM.bounds == (8.39, 8.39)
    assert patched.reactions.ATPM.bounds == (5.0, 5.0)
    repeated, _ = apply_profile(patched, profile)
    assert inspect_reaction(repeated, BIOMASS_ID)["metabolites"]["atp_c"] == -25.0
    assert provenance["profiles"][-1]["changes"][1]["kind"] == "absolute_stoichiometry"


def test_growth_is_biomass_even_when_objective_is_scaled(reference):
    configured, _ = apply_profile(reference, editable_profile(objective={"direction": "max", "coefficients": {BIOMASS_ID: 3.0}}))
    result = solve(configured)
    assert result["growth_rate_h"] == pytest.approx(0.2255827703, abs=1e-8)
    assert result["objective_value"] == pytest.approx(result["growth_rate_h"] * 3)


def test_infeasible_is_not_reported_as_zero_growth(reference):
    original = reference.reactions.EX_ch4_e.bounds
    result = solve(reference, uptake_caps={"EX_ch4_e": 0, "EX_o2_e": 0})
    assert result["status"] == "infeasible"
    assert result["growth_rate_h"] is None
    assert result["objective_value"] is None
    assert result["fluxes"] == {}
    assert not result["numerically_feasible"]
    assert reference.reactions.EX_ch4_e.bounds == original


@pytest.mark.parametrize("changes,match", [
    ({"reaction_bound": {}}, "Unknown profile"),
    ({"reaction_bounds": {"EX_typo_e": {"lower_bound": -1}}}, "Unknown reaction"),
    ({"reaction_bounds": {"EX_ch4_e": {"lower": -1}}}, "Unknown bounds"),
    ({"reaction_bounds": {"EX_ch4_e": {"lower_bound": 1}}}, "Inverted bounds"),
    ({"reaction_bounds": {"EX_ch4_e": {"lower_bound": float("nan")}}}, "finite"),
    ({"reaction_bounds": {"EX_ch4_e": {"lower_bound": 10**1000}}}, "finite"),
    ({"reaction_bounds": {"EX_ch4_e": {"lower_bound": True}}}, "boolean"),
    ({"stoichiometry": {BIOMASS_ID: {"typo_c": -1}}}, "Unknown metabolite"),
    ({"stoichiometry": {BIOMASS_ID: {"atp_c": float("inf")}}}, "finite"),
    ({"objective": {"direction": "MAX", "coefficients": {BIOMASS_ID: 1}}}, "direction"),
    ({"objective": {"direction": "max", "coefficients": {BIOMASS_ID: 0}}}, "nonzero"),
])
def test_invalid_profile_is_rejected_before_mutation(baseline, changes, match):
    before = cobra.io.to_json(baseline)
    with pytest.raises(ProfileError, match=match):
        apply_profile(baseline, editable_profile(**changes))
    assert cobra.io.to_json(baseline) == before


@pytest.mark.parametrize("caps", [
    {"EX_typo_e": 2}, {"EX_ch4_e": -1}, {"EX_ch4_e": float("inf")}, {"EX_ch4_e": True}, {"ATPM": 8},
])
def test_invalid_caps(reference, caps):
    with pytest.raises(ProfileError):
        solve(reference, uptake_caps=caps)


def test_duplicate_json_fields_rejected(tmp_path):
    source = tmp_path / "duplicate.json"
    source.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(ProfileError, match="Duplicate JSON field"):
        load_profile(source)


@pytest.mark.parametrize("format,suffix,loader", [("json", "json", cobra.io.load_json_model), ("sbml", "xml", cobra.io.read_sbml_model)])
def test_export_roundtrip_and_audit_manifest(reference, tmp_path, format, suffix, loader):
    patched, _ = apply_profile(reference, editable_profile(stoichiometry={BIOMASS_ID: {"atp_c": -24.0}}))
    path = tmp_path / f"configured.{suffix}"
    output = export_model(patched, path, format=format)
    restored = loader(str(path))
    assert model_info(restored)["counts"] == BASELINE_COUNTS
    assert inspect_reaction(restored, BIOMASS_ID)["metabolites"]["atp_c"] == -24.0
    assert restored.reactions.EX_nh4_e.lower_bound == -2.3
    manifest = json.loads((tmp_path / f"configured.{suffix}.provenance.json").read_text())
    assert manifest["export_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest["provenance"]["baseline_sha256"] == BASELINE_SHA256
    assert output["model_path"] == str(path.resolve())
    with pytest.raises(FileExistsError):
        export_model(patched, path)


def test_baseline_cannot_be_export_target(reference):
    with pytest.raises(ValueError, match="immutable"):
        export_model(reference, baseline_path(), overwrite=True)


def test_cli_info_is_valid_json(capsys):
    from symbiont_imcbath.cli import main
    assert main(["info"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["counts"] == BASELINE_COUNTS
    assert result["software_versions"]["glpk"]


def test_cli_reports_infeasible_with_distinct_exit_code(capsys):
    from symbiont_imcbath.cli import main
    assert main(["simulate", "--uptake-cap", "EX_ch4_e=0", "--uptake-cap", "EX_o2_e=0"]) == 3
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "infeasible"
    assert result["growth_rate_h"] is None


def test_cli_protects_baseline_output(capsys):
    from symbiont_imcbath.cli import main
    assert main(["info", "--output", str(baseline_path())]) == 2
    assert "immutable" in json.loads(capsys.readouterr().err)["message"]
    assert hashlib.sha256(baseline_path().read_bytes()).hexdigest() == BASELINE_SHA256


def test_cli_argument_errors_are_json(capsys):
    from symbiont_imcbath.cli import main
    assert main(["simulate", "--typo"]) == 2
    assert json.loads(capsys.readouterr().err)["status"] == "error"


@pytest.mark.parametrize("target", ["model", "manifest"])
def test_cli_rejects_export_response_path_collision_before_writing(tmp_path, capsys, target):
    from symbiont_imcbath.cli import main
    destination = tmp_path / "model.json"
    manifest = tmp_path / "model.json.provenance.json"
    response = destination if target == "model" else manifest
    # An equivalent, noncanonical path must still be recognized as a collision.
    response_alias = tmp_path / "unused" / ".." / response.name
    assert main(["export", str(destination), "--output", str(response_alias), "--force"]) == 2
    assert "separate" in json.loads(capsys.readouterr().err)["message"]
    assert not destination.exists()
    assert not manifest.exists()
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize("contents,expected", [
    ('{"schema_version":1,"schema_version":1}', "Duplicate JSON field"),
    ('{"nested":{"flow":1,"flow":2}}', "Duplicate JSON field"),
    ('{"value":NaN}', "finite"),
    ('{"value":Infinity}', "finite"),
    ('{"value":1e999}', "finite"),
])
def test_cli_replay_rejects_ambiguous_json(tmp_path, capsys, contents, expected):
    from symbiont_imcbath.cli import main
    source = tmp_path / "replay.json"
    source.write_text(contents, encoding="utf-8")
    response = tmp_path / "response.json"
    assert main(["replay", str(source), "--output", str(response)]) == 2
    assert expected in json.loads(capsys.readouterr().err)["message"]
    assert not response.exists()


@pytest.mark.parametrize("target", ["baseline", "model"])
def test_export_provenance_symlink_cannot_overwrite_protected_content(reference, tmp_path, target):
    destination = tmp_path / "model.json"
    manifest = tmp_path / "model.json.provenance.json"
    if target == "model":
        destination.write_text("existing model", encoding="utf-8")
    protected_target = baseline_path() if target == "baseline" else destination
    try:
        manifest.symlink_to(protected_target)
    except OSError:
        pytest.skip("Creating symbolic links is unavailable on this platform")
    before = protected_target.read_bytes()
    with pytest.raises(ValueError, match="immutable|separate"):
        export_model(reference, destination, overwrite=True)
    assert protected_target.read_bytes() == before
    if target == "baseline":
        assert not destination.exists()


@pytest.mark.parametrize("coefficient", [-2.0, 1.0])
def test_uptake_is_molecular_amount_when_exchange_is_scaled_or_reversed(reference, coefficient):
    configured, _ = apply_profile(reference, editable_profile(stoichiometry={"EX_pi_e": {"pi_e": coefficient}}))
    result = solve(configured)
    assert result["status"] == "optimal"
    assert result["growth_rate_h"] == pytest.approx(0.2255827703, abs=1e-8)
    reaction_flux = result["fluxes"]["EX_pi_e"]
    molecular_uptake = result["uptake_rates"]["EX_pi_e"]
    assert molecular_uptake > 0
    assert molecular_uptake == pytest.approx(coefficient * reaction_flux)
    # Extracellular phosphate has no other source: molecular uptake must match
    # actual phosphate consumed by its transport into the modeled cell.
    phosphate = configured.metabolites.get_by_id("pi_e")
    internal_consumption = -sum(
        reaction.metabolites[phosphate] * result["fluxes"][reaction.id]
        for reaction in phosphate.reactions if reaction.id != "EX_pi_e"
    )
    assert molecular_uptake == pytest.approx(internal_consumption, abs=1e-8)
