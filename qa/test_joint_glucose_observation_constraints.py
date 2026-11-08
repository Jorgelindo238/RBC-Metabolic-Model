"""Observational amount constraints do not invent kinetic or volume corrections."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("joint_glucose_observation_audit", ROOT / "scripts/audit_joint_glucose_observations.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_consistent_transport_and_positive_HK_amounts():
    r = module().interval_constraints([1, 4], [1, 1.1], [25, 24])
    assert r["constant_H_intersection"]["nonempty"]
    assert r["intervals"][0]["required_VHK_integrals_cell_mM"]["0.58"] > 0


def test_opposed_interval_geometry_bounds_are_not_kinetic_estimates():
    r = module().interval_constraints([1, 4, 8], [1, 1.2, 1.1], [25, 24.9, 25.2])
    assert not r["constant_H_intersection"]["nonempty"]
    assert not r["source_values_modified"]
    assert r["intervals"][0]["interval_constant_H_upper"] == pytest.approx(1/3)
    assert r["intervals"][1]["interval_constant_H_lower"] == pytest.approx(.75)
