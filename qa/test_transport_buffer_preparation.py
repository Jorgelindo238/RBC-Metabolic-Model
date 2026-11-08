"""Source temperature inference and closed synthetic carrier/buffer invariants."""

import copy
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_transport_buffer_synthetic import (rhs, sensitivity, simulate, symmetry_inputs, validate_config)


def config():
    return json.loads((ROOT / "config/fla_transport_buffer_synthetic.json").read_text())


@pytest.mark.parametrize("key", ["biological_fitting_allowed", "full_RBC_replay_allowed", "production_defaults_changed", "measured_initial_states_changed"])
def test_synthetic_preparation_never_enables_biology(key):
    c = config()
    c[key] = True
    with pytest.raises(ValueError):
        validate_config(c)


@pytest.mark.parametrize("h", [0, 1, -.1, float("nan"), True])
def test_invalid_geometry_rejected(h):
    c = config()
    c["geometry"]["hematocrit"] = h
    with pytest.raises(ValueError):
        validate_config(c)


@pytest.mark.parametrize("bad", [None, 0, -1, float("nan"), float("inf"), True])
def test_missing_capacity_rejected(bad):
    c = config()
    c["truth"]["beta_e"] = bad
    with pytest.raises(ValueError):
        validate_config(c)


def test_no_implicit_metabolic_acid_source():
    c = config()
    c["closure"]["sources_i_bag"] = .1
    with pytest.raises(ValueError):
        validate_config(c)


def test_optimizer_is_not_executed_in_preparation():
    c = config()
    c["future_recovery"]["optimizer_executed_in_preparation"] = True
    with pytest.raises(ValueError):
        validate_config(c)


@pytest.mark.parametrize("which,sign", [(0, 1), (1, -1)])
def test_truth_directions_and_signed_acid_amount_closure(which, sign):
    c = config()
    x = c["scenarios"][which]["initial"]
    h = c["geometry"]["hematocrit"]
    d = rhs(0, x, h=h, truth=c["truth"])
    assert np.sign(d[4]) == sign
    assert h * d[0] + (1 - h) * d[1] == pytest.approx(0)
    assert -h * c["truth"]["beta_i"] * d[2] - (1 - h) * c["truth"]["beta_e"] * d[3] == pytest.approx(0)
    assert np.sign(d[2]) == sign and np.sign(d[3]) == -sign


@pytest.mark.parametrize("boundary", [(0, 3), (3, 0), (0, 0)])
def test_constitutive_zero_boundary_invariance(boundary):
    c = config()
    x = np.array(c["scenarios"][0]["initial"])
    x[:2] = boundary
    d = rhs(0, x, h=c["geometry"]["hematocrit"], truth=c["truth"])
    for i, value in enumerate(boundary):
        if value == 0:
            assert d[i] >= 0


def test_negative_substrate_is_not_sanitized():
    c = config()
    x = np.array(c["scenarios"][0]["initial"])
    x[0] = -.01
    with pytest.raises(ValueError):
        rhs(0, x, h=c["geometry"]["hematocrit"], truth=c["truth"])


@pytest.mark.parametrize("which", [0, 1])
def test_unforced_truth_closes_and_preserves_configuration(which):
    c = config()
    before = copy.deepcopy(c)
    r = simulate(c, c["scenarios"][which])
    assert c == before
    assert np.min(r["states"][:2]) >= 0
    np.testing.assert_allclose(r["amount_residual"], 0, atol=1e-11)
    np.testing.assert_allclose(r["acid_residual"], 0, atol=1e-10)
    np.testing.assert_allclose(r["extent_state_residual"], 0, atol=1e-11)
    assert r["accepted_time"][-1] == c["horizon_day"][-1]


@pytest.mark.parametrize("which", [0, 1])
@pytest.mark.parametrize("scale", [.5, 2.])
def test_full_toy_unknown_Km_symmetry(which, scale):
    c = config()
    s = c["scenarios"][which]
    a = simulate(c, s)
    b = simulate(c, s, **symmetry_inputs(c, s, scale), time=a["time"])
    np.testing.assert_allclose(a["states"][:2], b["states"][:2], rtol=1e-7, atol=1e-9)
    np.testing.assert_allclose(a["states"][3], b["states"][3], atol=1e-8)
    np.testing.assert_allclose(b["states"][2] - a["states"][2], np.log10(scale), atol=1e-8)
    np.testing.assert_allclose(a["flux"], b["flux"], rtol=1e-6, atol=1e-9)


def test_km_known_case_does_not_have_the_same_full_rate_symmetry():
    c = config()
    s = c["scenarios"][0]
    a = rhs(0, s["initial"], h=.58, truth=c["truth"])[4]
    shifted = np.array(s["initial"])
    shifted[2] += np.log10(2)
    params = {**c["truth"], "access_i": c["truth"]["access_i"] * 2}
    b = rhs(0, shifted, h=.58, truth=params)[4]
    assert b != pytest.approx(a, rel=1e-3)


def test_holdout_does_not_enter_training_sensitivities():
    c = config()
    with pytest.raises(ValueError):
        sensitivity(c, c["scenarios"][0], [0, 10], step=1e-4)


@pytest.mark.parametrize("time", [[2, 1], [-1, 0], [0, 22], [0, float("nan")]])
def test_invalid_time_queries_rejected(time):
    c = config()
    with pytest.raises(ValueError):
        simulate(c, c["scenarios"][0], time=time)


def test_source_rounding_relation_reconstructed_when_original_available():
    spec = importlib.util.spec_from_file_location("source_processing_audit", ROOT / "scripts/audit_transport_source_processing.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not module.JBC.exists():
        pytest.skip("source workbook not available on this host")
    table, summary, _ = module.calculate()
    assert len(table) == 126 and summary["compatible_pairs"] == 126
    assert summary["pH22_independent_likelihood_allowed"] is False
    assert summary["pH4_extrapolation_allowed"] is False
    assert summary["maximum_candidate_residual_pH"] <= summary["rounding_bound_pH"]
