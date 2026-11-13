"""Focused checks for the read-only carbon audit."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("carbon_audit", Path(__file__).resolve().parents[1]/"scripts/audit_glucose_carbon.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_transport_cancels_only_in_amount_coordinates():
    h = .58
    names = ["GLC", "EGLC", "LAC", "ELAC"]
    volumes = audit.amount_coefficients(names, h)
    matrix = np.array([[1,0], [-h/(1-h),0], [0,-1], [0,h/(1-h)]])
    np.testing.assert_allclose(volumes @ matrix, 0, atol=1e-15)
    np.testing.assert_allclose(audit.amount_coefficients(names,h,True) @ matrix, 0, atol=1e-15)
    assert not np.allclose(np.ones(4) @ matrix, 0)


@pytest.mark.parametrize("h", [0,1,-.1,float("nan")])
def test_bad_geometry(h):
    with pytest.raises(ValueError):
        audit.amount_coefficients(["GLC"], h)


def test_signed_integrals_window_and_reversal():
    rates = np.array([[2.,-3.,5.,7.]])
    weights = np.array([.5,.5,1.,1.])
    intervals = np.array([0,0,1,2])
    np.testing.assert_allclose(audit.integral(rates,weights,intervals,1,2),[-.5])
    np.testing.assert_allclose(audit.integral(rates,weights,intervals,2,4),[12.])


def test_manifest_tampering(tmp_path):
    p = tmp_path/"data.txt"
    p.write_text("original")
    (tmp_path/"manifest.json").write_text(audit.json.dumps({p.name:audit.sha(p)}))
    assert audit.verify_manifest(tmp_path) == 1
    p.write_text("changed")
    with pytest.raises(ValueError):
        audit.verify_manifest(tmp_path)
