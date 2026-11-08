"""Explicit numerical adoption, reversibility and solver-comparison contracts."""

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(directory))

from equadiff_brodbar import equadiff_brodbar
from fla_working_reference import load_working_reference, reference_options
from verify_fla_working_reference import compare_arrays


def state():
    result = np.r_[np.full(113, 0.2), 7.2]
    result[13] = 2e-4
    return result


def test_working_profile_is_strict_consistent_and_calibration_remains_blocked():
    config = load_working_reference()
    before = copy.deepcopy(config)
    ode, solver = reference_options(config)
    assert ode == {"positivity_policy": "reaction_consistent", "curve_fit_strength": 0.0,
                   "reaction_availability_threshold": 1e-3}
    assert solver == {"method": "BDF", "rtol": 1e-7, "atol": 1e-9}
    assert config["calibration_allowed"] is False
    assert config["kinetic_parameters_promoted"] is False
    assert config == before


def test_historical_reference_explicitly_preserves_legacy():
    config = load_working_reference()
    ode, solver = reference_options(config, historical=True)
    assert ode == {"positivity_policy": "legacy", "curve_fit_strength": 0.0}
    np.testing.assert_array_equal(equadiff_brodbar(1.0, state(), **ode), equadiff_brodbar(1.0, state()))
    assert solver["rtol"] == 1e-7


def test_ultrastrict_override_is_numeric_not_a_kinetic_parameter():
    ode, solver = reference_options(load_working_reference(), ultrastrict=True, threshold=1e-4)
    assert ode["reaction_availability_threshold"] == 1e-4
    assert "custom_params" not in ode
    assert solver == {"method": "BDF", "rtol": 1e-8, "atol": 1e-10}


@pytest.mark.parametrize("kwargs", [{"threshold": 1e-3}, {"ultrastrict": True}])
def test_historical_mode_cannot_silently_apply_new_overrides(kwargs):
    with pytest.raises(ValueError, match="historical"):
        reference_options(load_working_reference(), historical=True, **kwargs)


@pytest.mark.parametrize("field", ["calibration_allowed", "kinetic_parameters_promoted"])
def test_config_cannot_enable_calibration_by_a_boolean_override(tmp_path, field):
    config = load_working_reference()
    config[field] = True
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="calibration"):
        load_working_reference(path)


def test_explicit_default_threshold_is_bit_identical_to_existing_policy():
    x = state()
    default = equadiff_brodbar(1.0, x, positivity_policy="reaction_consistent")
    explicit = equadiff_brodbar(1.0, x, positivity_policy="reaction_consistent", reaction_availability_threshold=1e-3)
    np.testing.assert_array_equal(default, explicit)


@pytest.mark.parametrize("bad", [0.0, -1.0, np.nan, np.inf, True, "0.001"])
def test_kernel_rejects_invalid_numerical_thresholds(bad):
    with pytest.raises(ValueError, match="threshold"):
        equadiff_brodbar(1.0, state(), positivity_policy="reaction_consistent", reaction_availability_threshold=bad)


def test_kernel_legacy_rejects_a_threshold_instead_of_ignoring_it():
    with pytest.raises(ValueError, match="reaction_consistent"):
        equadiff_brodbar(1.0, state(), reaction_availability_threshold=1e-3)


def test_threshold_changes_effective_not_native_rates_at_fixed_state():
    first, second = {}, {}
    for threshold, audit in ((1e-4, first), (1e-2, second)):
        equadiff_brodbar(1.0, state(), positivity_policy="reaction_consistent",
                         reaction_availability_threshold=threshold, numerical_audit=audit)
        assert audit["availability_threshold_mM"] == threshold
    assert first["raw_fluxes"] == second["raw_fluxes"]
    assert first["effective_fluxes"]["VPGK"] > second["effective_fluxes"]["VPGK"]


@pytest.mark.parametrize("threshold", [1e-4, 1e-3, 1e-2])
def test_every_zero_boundary_is_safe_at_each_predeclared_threshold(threshold):
    for index in range(113):
        x = state()
        x[index] = 0.0
        derivative = equadiff_brodbar(1.0, x, positivity_policy="reaction_consistent",
                                     reaction_availability_threshold=threshold)
        assert derivative[index] >= -1e-12


def test_convergence_uses_absolute_tolerance_for_near_zero_signed_quantities():
    maximum, passes = compare_arrays([[-1e-7, 0.0], [1.0, 1.1]], [[0.0, 0.0], [1.0, 1.0]], atol=1e-5, rtol=0.01)
    np.testing.assert_array_equal(passes, [True, False])
    np.testing.assert_allclose(maximum, [1e-7, 0.1])


@pytest.mark.parametrize("left,right", [([[np.nan]], [[0.0]]), ([[1.0, 2.0]], [[1.0]]), ([], [])])
def test_comparison_rejects_missing_or_invalid_evidence(left, right):
    with pytest.raises(ValueError):
        compare_arrays(left, right, atol=1e-5, rtol=0.01)
