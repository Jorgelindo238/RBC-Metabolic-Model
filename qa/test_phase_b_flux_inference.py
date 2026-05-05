"""Phase B tests for online flux inference and fixed feature vectors."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import MM_calibration as mm  # noqa: E402
import rbc_stoichiometry as rs  # noqa: E402
from flux_inference import infer_user_fluxes  # noqa: E402
from ml_features import (  # noqa: E402
    FEATURE_SCHEMA,
    FEATURE_VERSION,
    METABOLITE_FEATURES,
    REACTION_FEATURES,
    build_feature_payload,
    build_feature_schema,
)


def _bordbar_exp_data(names: tuple[str, ...]) -> tuple[np.ndarray, dict[str, list[float]]]:
    time_exp, exp_values, name_to_row = mm.load_experimental_data()
    exp_data = {
        name: [float(v) for v in exp_values[name_to_row[name], :]]
        for name in names
    }
    return np.asarray(time_exp, dtype=float), exp_data


def _nrmse(actual: np.ndarray, expected: np.ndarray) -> float:
    scale = max(float(np.mean(np.abs(expected))), 1e-12)
    return float(np.sqrt(np.mean((actual - expected) ** 2)) / scale)


def test_infer_user_fluxes_recovers_bordbar_teacher_flux_anchors():
    time_exp, exp_data = _bordbar_exp_data(("EGLC", "ELAC", "LAC"))

    result = infer_user_fluxes(
        exp_data,
        time_exp,
        rs.STOICHIOMETRY,
        reactions=("VEGLC", "VELAC", "VLDH"),
    )

    dense_time = np.asarray(result["time"], dtype=float)
    expected_veglc = -PchipInterpolator(time_exp, exp_data["EGLC"]).derivative()(dense_time)
    expected_velac = PchipInterpolator(time_exp, exp_data["ELAC"]).derivative()(dense_time)
    expected_vldh = PchipInterpolator(time_exp, exp_data["LAC"]).derivative()(dense_time) + expected_velac

    fluxes = result["fluxes"]
    assert _nrmse(fluxes["VEGLC"], expected_veglc) < 1e-9
    assert _nrmse(fluxes["VELAC"], expected_velac) < 1e-9
    assert _nrmse(fluxes["VLDH"], expected_vldh) < 1e-9

    confidence = result["confidence"]
    assert confidence["VEGLC"]["method"] == "stoichiometric_singleton"
    assert confidence["VELAC"]["method"] == "stoichiometric_singleton"
    assert confidence["VLDH"]["method"] == "stoichiometric_singleton"
    assert confidence["VEGLC"]["confidence"] > 0.8
    assert confidence["VLDH"]["confidence"] > 0.8


def test_feature_payload_has_stable_schema_and_finite_values():
    time_exp, exp_data = _bordbar_exp_data(("EGLC", "ELAC", "LAC"))
    inferred = infer_user_fluxes(
        exp_data,
        time_exp,
        rs.STOICHIOMETRY,
        reactions=("VEGLC", "VELAC", "VLDH"),
    )

    payload = build_feature_payload(
        inferred["curves"],
        inferred["fluxes"],
        inferred["time"],
        metabolites=("ATP", "EGLC", "ELAC"),
        reactions=("VEGLC", "VELAC", "VLDH"),
    )

    schema = payload["schema"]
    values = np.asarray(payload["values"], dtype=float)
    assert payload["feature_version"] == FEATURE_VERSION
    assert len(schema) == 3 * len(METABOLITE_FEATURES) + 3 * len(REACTION_FEATURES)
    assert values.shape == (len(schema),)
    assert np.all(np.isfinite(values))

    eglc_present = schema.index("metabolite:EGLC:present")
    atp_present = schema.index("metabolite:ATP:present")
    vldh_present = schema.index("reaction:VLDH:present")
    assert values[eglc_present] == 1.0
    assert values[atp_present] == 0.0
    assert values[vldh_present] == 1.0


def test_feature_schema_default_is_stable_and_missing_series_are_zeroed():
    assert FEATURE_VERSION == "phase_b_v1"
    assert FEATURE_SCHEMA == build_feature_schema()

    payload = build_feature_payload(
        curves={"EGLC": [25.0, 24.0]},
        fluxes={},
        time_grid=[1.0, 2.0],
        metabolites=("EGLC", "ATP"),
        reactions=("VEGLC",),
    )

    schema = payload["schema"]
    values = np.asarray(payload["values"], dtype=float)
    assert np.all(np.isfinite(values))
    assert values[schema.index("metabolite:EGLC:present")] == 1.0
    assert values[schema.index("metabolite:ATP:present")] == 0.0
    assert values[schema.index("reaction:VEGLC:present")] == 0.0
