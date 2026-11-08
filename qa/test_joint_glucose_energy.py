"""Source-extracted RHS parity and honest joint-observation parameterization."""

import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import equadiff_brodbar as kernel
from fla_joint_calibration import JointRHS, COORDINATES, GROUPS, joint_score, resolve_capacities, scalar_mm, unpack
from rbc_glut_only_transport import equadiff_glut_only


def context():
    p = json.loads((ROOT / "output/exploratory_energy_sensitivity_J1_J4_2026_10_06/frozen_parameters.json").read_text())
    k = json.loads((ROOT / "config/fla_glucose_real_candidate.json").read_text())["glucose_kinetics"]
    x = np.load(ROOT / "output/exploratory_energy_sensitivity_J1_J4_2026_10_06/frozen_initial_state.npz")["states"]
    d = json.loads((ROOT / "config/fla_joint_glucose_energy.json").read_text())
    return p, k, x, d


@pytest.mark.parametrize("seed", range(5))
def test_all_raw_executed_rates_and_rhs_match_native(seed):
    p, k, x, d = context()
    rng = np.random.default_rng(seed)
    if seed:
        x[:113] = np.exp(rng.uniform(-12, 3, 113))
        x[rng.choice(113, 10, replace=False)] = 0
        factors = np.exp(rng.uniform(np.log([.1,.02,.001,.25,.25,.001]), np.log([4,1,2,16,32,1])))
        p, k, _ = unpack(np.log(factors), p, k, resolve_capacities(p), d["factor_bounds"])
    before, params = x.copy(), copy.deepcopy(p)
    fast = JointRHS(p, k)
    audit = {}
    expected = equadiff_glut_only(3., x, glucose_kinetics=k, hematocrit=.58, custom_params=p,
        numerical_audit=audit, ph_policy="clamped_diagnostic", positivity_policy="reaction_consistent",
        curve_fit_strength=0., reaction_availability_threshold=.001)
    raw, executed, _ = fast.rates(3., x)
    np.testing.assert_array_equal(raw, [audit["raw_fluxes"][r] for r in fast.reactions])
    np.testing.assert_array_equal(executed, [audit["effective_fluxes"][r] for r in fast.reactions])
    np.testing.assert_array_equal(fast(3., x), expected)
    np.testing.assert_array_equal(x, before)
    assert p == params and kernel.mm is not scalar_mm


@pytest.mark.parametrize("value", [0., 1e-12, .01, 1., 1e8, -1.])
def test_scalar_mm_retains_exact_boundary_and_power_rule(value):
    for km in (0., .1, 10.):
        for hill in (1., 1.5, 2.):
            assert scalar_mm(np.float64(value), km, hill) == kernel.mm(np.float64(value), km, hill)


def test_capacity_groups_preserve_reverse_ratio_and_HK_ceiling():
    p, k, _, d = context()
    pp, kk, factors = unpack(np.log([2,.5,.1,4,8,.1]), p, k, resolve_capacities(p), d["factor_bounds"])
    assert pp["vmax_VAK"] / pp["vmax_VAK_rev"] == pytest.approx(p["vmax_VAK"]/p["vmax_VAK_rev"])
    assert pp["vmax_VHK"] == 2.5 and kk["km_e"] == k["km_e"]
    changed = {name for name in pp if pp[name] != p.get(name)}
    assert changed == {name for members in GROUPS.values() for name in members}
    assert set(factors) == set(COORDINATES)
    with pytest.raises(ValueError):
        unpack(np.log([1,1.01,1,1,1,1]), p, k, resolve_capacities(p), d["factor_bounds"])


@pytest.mark.parametrize("seed", [11, 22, 33])
def test_structural_jacobian_support_includes_checked_finite_differences(seed):
    p, k, _, _ = context()
    rhs = JointRHS(p, k)
    rng = np.random.default_rng(seed)
    x = np.r_[np.exp(rng.uniform(-9, 2, 113)), 7.2]
    base = rhs(2., x)
    for j in range(114):
        other = x.copy()
        other[j] += max(abs(x[j])*.001, 1e-7)
        difference = rhs(2., other)-base
        assert not np.any((np.abs(difference) > 1e-12) & ~rhs.jacobian_sparsity[:,j])


def test_pooled_profile_matches_independent_full_normalized_likelihood():
    obs = np.arange(1., 15.).reshape(7,2)
    pred = obs * np.linspace(.5, 1.5, 14).reshape(7,2)
    r = joint_score(pred, obs)
    def f(logv):
        v = np.exp(logv)
        residual = np.log(obs)-np.log(pred)+v/2
        return float(np.sum(.5*residual**2/v+np.log(obs)+.5*np.log(2*np.pi*v)))
    fit = minimize_scalar(f, bounds=(-20, 3), method="bounded")
    assert fit.fun == pytest.approx(r["negative_log_likelihood"], abs=1e-9)
    assert r["count"] == 14 and not r["teachers_independent_likelihood_terms"]


@pytest.mark.parametrize("kind", ["zero", "negative", "nan", "shape", "empty"])
def test_no_missing_or_zero_likelihood_imputation(kind):
    pred, obs = np.ones((7,2))*.9, np.ones((7,2))
    if kind == "zero": obs[0,0] = 0
    if kind == "negative": pred[0,0] = -1
    if kind == "nan": obs[1,0] = np.nan
    if kind == "shape": obs = obs[:6]
    if kind == "empty": pred, obs = pred[:,:0], obs[:,:0]
    with pytest.raises(ValueError): joint_score(pred, obs)
