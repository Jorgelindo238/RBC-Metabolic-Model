"""Profiled noise normalizers and conditional real-pilot temporal isolation."""

import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_profiled_observation_noise import profile_lognormal_dispersion
from fla_real_glucose_pilot import glucose_driver, predict_glucose, training_score


def test_profile_matches_independent_scalar_variance_optimization():
    pred, obs = np.array([20., 18., 16., 14.]), np.array([21., 17., 17., 13.])
    result = profile_lognormal_dispersion(pred, obs)
    d = np.log(obs/pred)
    def nll(logv):
        v = np.exp(logv)
        return .5*np.sum((d+.5*v)**2/v)+np.log(obs).sum()+.5*len(obs)*np.log(2*np.pi*v)
    fit = minimize_scalar(nll, bounds=(-20, 2), method="bounded", options={"xatol": 1e-12})
    assert np.exp(fit.x) == pytest.approx(result["log_variance"], rel=1e-6)
    assert fit.fun == pytest.approx(result["negative_log_likelihood"], abs=1e-10)


@pytest.mark.parametrize("observed", [[1, 2], [1, 0, 2], [1, -1, 2], [1, np.nan, 2], [1, 2, 3]])
def test_invalid_or_zero_dispersion_not_imputed(observed):
    with pytest.raises(ValueError):
        profile_lognormal_dispersion([1, 2, 3], observed)


def test_driver_ignores_future_intracellular_measurements():
    time = [1, 4, 8, 11, 15, 18]
    a = glucose_driver(time, [1, 2, 1, 2, 100, 200], 11)
    b = glucose_driver(time, [1, 2, 1, 2, 1, 1], 11)
    for t in np.linspace(1, 18, 30):
        assert a(t) == b(t)
    assert a(18) == 2


def test_conditional_prediction_and_profile_ignore_heldout_values():
    design = json.loads((ROOT / "config/fla_real_glucose_pilot.json").read_text())
    data = {"time": [1, 4, 8, 11, 15, 18, 22, 25, 29, 46], "GLC": [1.]*10,
            "EGLC": [25, 24, 23, 21, 20, 19, 18, 17, 16, 13], "kinetics": {"km_i": 3.5}}
    other = copy.deepcopy(data)
    other["GLC"][-2:] = [100, 100]
    other["EGLC"][-2:] = [1, 1]
    a, b = [predict_glucose(d, design, .03, 24) for d in (data, other)]
    np.testing.assert_array_equal(a["predicted_EGLC"], b["predicted_EGLC"])
    assert training_score(data, design, a) == training_score(other, design, b)
