"""Geometry, reversible equilibria, executed budgets and honest source keys."""

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from equadiff_brodbar import equadiff_brodbar
from rbc_distinct_volume_transport import (equadiff_distinct_volume, glut_import,
    mct_export, phase_matrix, volume_fractions)
from reaction_positivity import rbc_reaction_matrix


def state():
    return np.r_[np.full(113, 0.2), 7.2]


def kinetics():
    return {"glucose": {"conductance": .1, "km_i": 2, "km_e": 20},
            "lactate": {"conductance": .2, "km_i": 2, "km_e": 2}, "ph_reference": 7.2}


@pytest.mark.parametrize("policy", ["legacy", "reaction_consistent"])
def test_historical_mode_bit_identical(policy):
    x = state()
    np.testing.assert_array_equal(equadiff_distinct_volume(1, x, positivity_policy=policy),
                                  equadiff_brodbar(1, x, positivity_policy=policy))


@pytest.mark.parametrize("h", [0, 1, -.2, 1.2, float("nan"), float("inf"), True])
def test_invalid_hct_rejected(h):
    with pytest.raises(ValueError):
        volume_fractions(h)


@pytest.mark.parametrize("h", [.574, .58, .632])
def test_transport_columns_conserve_amounts(h):
    names, reactions, matrix, volumes, rate_volumes = phase_matrix(h)
    _, _, s = rbc_reaction_matrix()
    np.testing.assert_allclose(volumes[:, None] * matrix, s * rate_volumes, rtol=1e-14, atol=1e-15)
    for reaction, pair in (("VEGLC", ("GLC", "EGLC")), ("VELAC", ("LAC", "ELAC"))):
        column = reactions.index(reaction)
        assert sum(volumes[names.index(p)] * matrix[names.index(p), column] for p in pair) == pytest.approx(0)
    assert volumes[names.index("E4P")] == h
    assert volumes[names.index("EGLC")] == 1 - h
    assert rate_volumes[reactions.index("VECYT")] == h
    for reaction in ("VEGSH_deg", "VEGSSG_deg"):
        assert rate_volumes[reactions.index(reaction)] == 1 - h


@pytest.mark.parametrize("c", [0, .1, 10])
def test_glut_equal_activity_equilibrium_despite_asymmetric_km(c):
    assert glut_import(c, c, conductance=.2, km_i=3, km_e=30) == 0


def test_glut_reversible_and_haldane_directional_capacities():
    k, ki, ke = .2, 3., 30.
    assert glut_import(0, 1000000, conductance=k, km_i=ki, km_e=ke) == pytest.approx(k * ke, rel=1e-4)
    assert glut_import(1000000, 0, conductance=k, km_i=ki, km_e=ke) == pytest.approx(-k * ki, rel=1e-4)
    assert glut_import(0, 0, conductance=k, km_i=ki, km_e=ke) == 0


@pytest.mark.parametrize("phi,phe", [(7.2, 7.2), (6.8, 7.2), (7.2, 6.8)])
def test_mct_activity_equilibrium(phi, phe):
    le = 2.
    li = le * 10 ** (phi - phe)
    assert mct_export(li, le, phi=phi, phe=phe, conductance=.3, km_i=2, km_e=2, ph_reference=7.2) == pytest.approx(0, abs=1e-15)


def test_mct_ph_drives_sign_and_zero_substrate_boundary():
    p = dict(conductance=.3, km_i=2, km_e=2, ph_reference=7.2)
    assert mct_export(1, 1, phi=6.8, phe=7.2, **p) > 0
    assert mct_export(1, 1, phi=7.2, phe=6.8, **p) < 0
    assert mct_export(0, 0, phi=7.2, phe=7.2, **p) == 0


@pytest.mark.parametrize("name", ["GLC", "EGLC", "LAC", "ELAC"])
def test_reaction_consistent_zero_boundary_and_no_state_mutation(name):
    names, _, _, _, _ = phase_matrix(.58)
    x = state()
    x[names.index(name)] = 0
    before = x.copy()
    audit = {}
    d = equadiff_distinct_volume(1, x, mode="phase_glut_mct", hematocrit=.58,
        transport_kinetics=kinetics(), phe=7.2, ph_policy="clamped_diagnostic", numerical_audit=audit)
    assert d[names.index(name)] >= 0
    assert d[-1] == 0
    assert audit["MCT_proton_export_per_L_bag_day"] == .58 * audit["effective_fluxes"]["VELAC"]
    np.testing.assert_array_equal(x, before)


@pytest.mark.parametrize("kw", [{"positivity_policy": "legacy"}, {"curve_fit_strength": .1},
    {"ph_policy": "native"}, {"transport_kinetics": None}, {"phe": None}])
def test_unsafe_or_incomplete_phase_contract_rejected(kw):
    parameters = dict(mode="phase_glut_mct", hematocrit=.58, transport_kinetics=kinetics(),
                      phe=7.2, ph_policy="clamped_diagnostic")
    parameters.update(kw)
    with pytest.raises(ValueError):
        equadiff_distinct_volume(1, state(), **parameters)


def test_prepare_all_pairings_and_keys(tmp_path):
    spec = importlib.util.spec_from_file_location("prepare_phase", ROOT / "scripts/prepare_yurkovich_phase_keys.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    result = m.prepare(tmp_path / "data")
    assert result["source_samples"] == 372
    assert result["phase_records"] == 144
    assert result["donor_ids_verified"] == 0 and result["pairings"] == 6
    keys = list(__import__("csv").DictReader((tmp_path / "data/sample_keys.csv").open()))
    assert len({r["working_sample_key"] for r in keys}) == 372
    assert len({r["trajectory_key"] for r in keys}) == 36
    assert len({r["validation_split_key"] for r in keys}) == 1
    assert all(r["donor_id"] == "" for r in keys)
    h = json.loads((tmp_path / "data/hematocrit_scenarios.json").read_text())
    assert [r["hematocrit"] for r in h] == [.58, .574, .632]
