"""Explicit input-knot solver boundaries prevent skipped experimental forcing."""

import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_real_glucose_pilot_segmented import predict_glucose


def inputs():
    design = json.loads((ROOT / "config/fla_real_glucose_pilot_segmented.json").read_text())
    data = {"time": [1, 4, 8, 11, 15, 18, 22, 25, 29, 46],
            "GLC": [1, 1.3, 1.2, 1.1, 1.2, 1.05, 1.0, 1.0, .9, .8],
            "EGLC": [25, 24, 23, 21, 20, 19, 18, 17, 16, 13], "kinetics": {"km_i": 3.5}}
    return data, design


@pytest.mark.parametrize("km", [24., 500.])
def test_segmented_BDF_DOP853_and_exact_knots(km):
    data, design = inputs()
    a = predict_glucose(data, design, .03, km)
    b = predict_glucose(data, design, .03, km, method="DOP853")
    np.testing.assert_allclose(a["predicted_EGLC"], b["predicted_EGLC"], rtol=1e-7, atol=1e-7)
    assert all(t in a["accepted_time"] for t in data["time"] if t <= 25)
    assert a["predicted_EGLC"][0] == data["EGLC"][0]
    assert np.min(a["accepted_EGLC"]) > 0


@pytest.mark.parametrize("km", [24., 500.])
def test_segmented_future_measurements_do_not_leak(km):
    data, design = inputs()
    other = copy.deepcopy(data)
    other["GLC"][-2:] = [100, 100]
    other["EGLC"][-2:] = [1, 1]
    a, b = [predict_glucose(d, design, .03, km) for d in (data, other)]
    np.testing.assert_array_equal(a["predicted_EGLC"], b["predicted_EGLC"])
