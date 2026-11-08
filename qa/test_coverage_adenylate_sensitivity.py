import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src")); sys.path.insert(0, str(ROOT/"scripts"))
from rbc_coverage_extensions import BRANCHES, CoverageRHS, branch_rates, extend_matrix
from fla_joint_calibration import JointRHS
from fla_network_observation_coverage import channel_coverage, volume_conservation_diagnostic
from fla_adenylate_sensitivity import resolve_parameters, perturb, diagnostics, sensitivity_column, select_subset, admissibility, ADENYLATES
from fla_broad_protected_calibration import POOLS
from rbc_gem_audit import pool_mapping, project_gem


def rhs_context():
    p = {"vmax_VHK": .1, "vmax_VPFK": .489, "vmax_VOPLAH": 1.}
    k = {"conductance": .026, "km_i": 3.49, "km_e": 23.5}
    x = np.ones(114); x[-1] = 7.2
    return p, k, x


@pytest.mark.parametrize("kinetics", [None, {}, {"VACLY": {"vmax": 0., "km_CIT": 1., "km_ATP": 1., "km_COA": 1.}}])
def test_disabled_extension_has_bitwise_native_rollback_and_keeps_oplah(kinetics):
    p, k, x = rhs_context()
    native, extension = JointRHS(p, k), CoverageRHS(p, k, branch_kinetics=kinetics)
    np.testing.assert_array_equal(extension(1., x), native(1., x))
    for a, b in zip(extension.rates(1., x), native.rates(1., x)): np.testing.assert_array_equal(a, b)
    assert native.rates(1., x)[1][native.reactions.index("VOPLAH")] > 0


def test_branches_match_pinned_gem_without_discarding_non_currency_species():
    path = ROOT/"output/rbc_gem_network_audit_2026_10_06/github/1.3.0/model/RBC-GEM.json"
    model = json.loads(path.read_text())
    inverse = {v:k for k, v in pool_mapping(model).items()}
    for branch in BRANCHES.values():
        r = next(r for r in model["reactions"] if r["id"] == branch["gem_id"])
        projected, missing, _ = project_gem(r, inverse)
        assert not missing and projected == branch["stoichiometry"]


@pytest.mark.parametrize("pool", ["ATP", "COA", "CIT"])
def test_citrate_lyase_requires_all_substrates_and_never_adds_an_atp_source(pool):
    p, k, x = rhs_context()
    ext = CoverageRHS(p, k, branch_kinetics={"VACLY": {"vmax": 1., "km_CIT": 1., "km_ATP": 1., "km_COA": 1.}})
    x[ext.names.index(pool)] = 0
    raw, executed, _ = ext.rates(1., x)
    assert raw[-1] == executed[-1] == 0
    assert ext.matrix[ext.names.index("ATP"), -1] == -1
    assert ext.matrix[ext.names.index("ADP"), -1] == 1


def test_one_availability_factor_scales_all_branch_terms():
    p, k, x = rhs_context()
    ext = CoverageRHS(p, k, branch_kinetics={"VACLY": {"vmax": 1., "km_CIT": 1., "km_ATP": 1., "km_COA": 1.}})
    x[ext.names.index("ATP")] = .0002
    raw, executed, factors = ext.rates(1., x)
    assert factors[-1] == pytest.approx(.2) and executed[-1] == pytest.approx(.2*raw[-1])
    assert ext.matrix[ext.names.index("ATP"), -1]*executed[-1] == -ext.matrix[ext.names.index("ADP"), -1]*executed[-1]


@pytest.mark.parametrize("params", [{"VACLY": {"vmax": 1.}}, {"NO_sink": {"vmax": 1.}},
    {"VARGN": {"vmax": -1., "km_ARG": 1.}}, {"VARGN": {"vmax": 1., "km_ARG": 0.}}])
def test_branch_activation_requires_explicit_valid_kinetics(params):
    p, k, x = rhs_context()
    with pytest.raises(ValueError): CoverageRHS(p, k, branch_kinetics=params)


def test_coverage_extension_breaks_only_supported_invariants_and_leaves_citr_static():
    p, k, _ = rhs_context(); rhs = JointRHS(p, k)
    reactions, m = extend_matrix(rhs.names, rhs.reactions, rhs.matrix, enabled=list(BRANCHES))
    assert not np.any(m[rhs.names.index("CITR")])
    for cell, extra in (("CIT", "ECIT"), ("ARG", "EARG")):
        old = rhs.matrix[rhs.names.index(cell)]+(.42/.58)*rhs.matrix[rhs.names.index(extra)]
        new = m[rhs.names.index(cell)]+(.42/.58)*m[rhs.names.index(extra)]
        assert np.allclose(old, 0, atol=1e-15) and not np.allclose(new, 0)
    assert len(reactions) == len(rhs.reactions)+2


def test_both_phase_concentrations_falling_cannot_be_fixed_by_a_constant_hematocrit():
    d = volume_conservation_diagnostic([2., 1.], [4., 3.], [1., 4.], .58)
    assert d["any_interval_has_no_physical_constant_H"] and not d["H_fitted_or_measured"]


def test_volume_cancellation_identifies_a_physical_h_without_fitting_it():
    d = volume_conservation_diagnostic([1., 2.], [2., 1.], [1., 4.], .5)
    assert d["intervals"][0]["exact_constant_H_implied"] == .5
    assert not d["any_interval_has_no_physical_constant_H"]


def test_static_observation_is_blocked_not_deleted():
    d = channel_coverage(np.array([[0.], [1.]]), ["CITR", "ATP"], {"CITR": [1., 2.], "ATP": [1., 1.]}, [1., 4.], actively_fitted=["ATP"])
    assert d[0]["source_retained"] and d[0]["status"] == "blocked_static_dynamics"
    assert d[1]["status"] == "conditional_fitting_scope"


def test_parameter_defaults_come_from_native_source_and_perturb_one_value_only():
    d = json.loads((ROOT/"config/fla_coverage_adenylate_sensitivity.json").read_text())
    p = {"vmax_VAK": .4, "frozen": 9.}
    values = resolve_parameters(p, ROOT/"src/equadiff_brodbar.py", d["parameters"])
    assert len(values) == 25 and values["vmax_VAK"]["value"] == .4
    assert values["km_B13PG"]["source"] == "native_literal_default"
    changed = perturb(p, "vmax_VAK", .4, np.log(1.05))
    assert changed["frozen"] == 9 and changed["vmax_VAK"] == pytest.approx(.42) and p["vmax_VAK"] == .4
    with pytest.raises(ValueError): resolve_parameters(p, ROOT/"src/equadiff_brodbar.py", ["invented_parameter"])


def test_log_sensitivity_recovers_a_known_elasticity_with_two_steps():
    y = np.ones((11, 4)); scales = {"absolute": [1.]*11, "relative": .2}
    h = np.log(1.05)
    c = sensitivity_column(y*np.exp(2*h), y*np.exp(-2*h), y*np.exp(h), y*np.exp(-h), y, scales, h)
    assert np.allclose(c["log_adenylate_derivative"], 2.) and c["relative_two_step_disagreement"] < 1e-12


def test_adenylate_totals_and_energy_charge_are_derived_not_extra_observations():
    y = np.ones((11, 4)); scales = {"absolute": [1.]*11, "relative": .2}
    r = diagnostics(y, y, scales)
    assert r["energy_charge"] == [.5]*4 and not r["derived_metrics_are_independent_observations"]
    zero = y.copy(); zero[POOLS.index("ATP")] = 0
    with pytest.raises(ValueError): diagnostics(zero, y, scales)


def test_subset_rejects_regression_and_correlated_duplicates():
    d = json.loads((ROOT/"config/fla_coverage_adenylate_sensitivity.json").read_text())
    base = {"adenylate_log_residuals": [-1.]*12, "adenylate_log_MSE": {p:1. for p in ADENYLATES},
            "working_MSE": {p:1. for p in POOLS}, "adenylate_log_mean": 1.}
    def column(vector, regression=False):
        diag = copy.deepcopy(base); diag["adenylate_log_mean"] = .9
        diag["adenylate_log_MSE"] = {p:.9 for p in ADENYLATES}
        if regression: diag["working_MSE"]["F6P"] = 2.
        return {"log_adenylate_derivative": vector, "relative_two_step_disagreement": 0., "response_norm": float(np.linalg.norm(vector)),
            "directional_probes": {k:{"label": k, "diagnostics": diag} for k in ("plus", "minus")}}
    columns = {"a":column([1.]*12), "b":column([1.]*12), "bad":column([1., 0.]*6, True)}
    ranking, chosen = select_subset(columns, base, 0., d)
    assert len(chosen) == 1 and chosen[0]["parameter"] in ("a", "b")
    assert not next(r for r in ranking if r["parameter"] == "bad")["eligible_for_subset"]


def test_aprt_zero_is_not_silently_activated_by_log_perturbations():
    with pytest.raises(ValueError): resolve_parameters({"vmax_VAPRT": 0.}, ROOT/"src/equadiff_brodbar.py", ["vmax_VAPRT"])


def test_individual_adenylate_regression_cannot_hide_in_an_improved_mean():
    d = json.loads((ROOT/"config/fla_coverage_adenylate_sensitivity.json").read_text())
    base = {"adenylate_log_MSE": {p:1. for p in ADENYLATES}, "working_MSE": {p:1. for p in POOLS}, "adenylate_log_mean": 1.}
    new = copy.deepcopy(base); new["adenylate_log_mean"] = .8; new["adenylate_log_MSE"]["ATP"] = 2.
    r = admissibility(new, base, d)
    assert r["gain_pass"] and not r["individual_adenylate_pass"]
