"""No implicit free pools, pH-temperature transfer, or proton creation."""

import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_transport_access_ph import (PoolAccess, buffered_rates, clamped_reservoirs,
                                     export_bound, lactate_drive, readiness)
from rbc_distinct_volume_transport import glut_import, mct_export


def config():
    return json.loads((ROOT / "config/fla_transport_access_ph_contract.json").read_text())


def test_pool_operator_uses_phase_water_recovery_and_free_fraction():
    p = PoolAccess(free_fraction=.6, aqueous_fraction=.75, recovery_fraction=.8, activity_coefficient=.9)
    assert p.activity_mM(2) == pytest.approx(1.8)
    assert p.activity_mM(0) == 0


@pytest.mark.parametrize("key", ["free_fraction", "aqueous_fraction", "recovery_fraction", "activity_coefficient"])
@pytest.mark.parametrize("bad", [None, True, float("nan"), float("inf"), -1])
def test_unknown_or_invalid_pool_factor_rejected(key, bad):
    values = dict(free_fraction=1, aqueous_fraction=1, recovery_fraction=1, activity_coefficient=1)
    values[key] = bad
    with pytest.raises(ValueError):
        PoolAccess(**values)


@pytest.mark.parametrize("key", ["aqueous_fraction", "recovery_fraction"])
@pytest.mark.parametrize("bad", [0, 1.01])
def test_water_and_recovery_bounded_nonzero(key, bad):
    values = dict(free_fraction=1, aqueous_fraction=1, recovery_fraction=1, activity_coefficient=1)
    values[key] = bad
    with pytest.raises(ValueError):
        PoolAccess(**values)


def test_free_fraction_can_be_zero_but_not_negative_or_over_one():
    assert PoolAccess(0, 1, 1, 1).activity_mM(4) == 0
    with pytest.raises(ValueError):
        PoolAccess(1.1, 1, 1, 1)
    with pytest.raises(ValueError):
        PoolAccess(1, 1, 1, 1).activity_mM(-.1)


@pytest.mark.parametrize("rho", [.5, 1, 2, 4])
@pytest.mark.parametrize("delta", [-1, -.5, -.2, 0, .2])
def test_direction_and_accessibility_ph_confounding(rho, delta):
    li, le = 1.2, 3.5
    drive = lactate_drive(li, le, accessibility_ratio=rho, delta_pH=delta)
    assert (drive > 0) == (delta < export_bound(li, le, rho))
    same = lactate_drive(li, le, accessibility_ratio=1, delta_pH=delta - np.log10(rho))
    assert drive / rho == pytest.approx(same)


@pytest.mark.parametrize("rho", [.5, 1, 2, 4])
def test_exact_reduced_mct_equilibrium_uses_activities(rho):
    li, le, phe = 1.2, 3.5, 7.2
    delta = export_bound(li, le, rho)
    j = mct_export(rho * li, le, phi=phe + delta, phe=phe,
                   conductance=.3, km_i=2, km_e=2, ph_reference=7.2)
    assert j == pytest.approx(0, abs=1e-14)
    assert lactate_drive(li, le, accessibility_ratio=rho, delta_pH=delta) == pytest.approx(0, abs=1e-14)


def test_glucose_equilibrium_is_equal_accessible_activity_not_equal_extract():
    intracellular = PoolAccess(1, .5, 1, 1).activity_mM(2)
    extracellular = PoolAccess(1, 1, 1, 1).activity_mM(4)
    assert glut_import(intracellular, extracellular, conductance=.1, km_i=2, km_e=20) == 0


@pytest.mark.parametrize("li,le,expected", [(0, 2, -2), (2, 0, 2), (0, 0, 0)])
def test_zero_boundaries_without_logarithm(li, le, expected):
    assert lactate_drive(li, le, accessibility_ratio=1, delta_pH=0) == expected
    with pytest.raises(ValueError):
        export_bound(li, le, 1)


@pytest.mark.parametrize("h", [.574, .58, .632])
@pytest.mark.parametrize("q", [-.4, 0, .4])
@pytest.mark.parametrize("source", [(0, 0), (.3, -.1)])
def test_buffer_acid_conservation_and_clamp_reservoir(h, q, source):
    si, se = source
    bi, be = 65, 10
    pi, pe = buffered_rates(q, hct=h, beta_i=bi, beta_e=be, source_i_bag=si, source_e_bag=se)
    assert -h * bi * pi - (1 - h) * be * pe == pytest.approx(si + se, abs=1e-14)
    ri, re = clamped_reservoirs(q, source_i_bag=si, source_e_bag=se)
    assert si - q + ri == pytest.approx(0, abs=1e-14)
    assert se + q + re == pytest.approx(0, abs=1e-14)


@pytest.mark.parametrize("q", [-1, 1])
def test_mct_only_feedback_resists_transport_direction(q):
    pi, pe = buffered_rates(q, hct=.6, beta_i=65, beta_e=10, source_i_bag=0, source_e_bag=0)
    assert np.sign(pi) == np.sign(q)
    assert np.sign(pe) == -np.sign(q)
    assert np.sign(pi - pe) == np.sign(q)


@pytest.mark.parametrize("key,bad", [("hct", 0), ("hct", 1), ("beta_i", 0), ("beta_e", -1),
                                   ("q_export_bag", float("nan")), ("source_i_bag", None)])
def test_no_implicit_buffer_inputs(key, bad):
    values = dict(q_export_bag=1, hct=.6, beta_i=65, beta_e=10, source_i_bag=0, source_e_bag=0)
    values[key] = bad
    with pytest.raises(ValueError):
        buffered_rates(**values)


def test_working_contract_stays_unready_and_originals_unchanged():
    c = config()
    before = copy.deepcopy(c)
    result = readiness(c)
    assert len(result["missing"]) == 14
    assert not result["prerequisite_inventory_complete"]
    assert not result["free_pH_prediction_authorized"]
    assert not result["optimization_authorized"]
    assert c == before
    assert not c["concentration_basis"]["ufba_applied"]
    assert not c["kinetics"]["legacy_pH_terms_reused"]


@pytest.mark.parametrize("temperature", [22, 37, None])
def test_observed_assay_temperature_cannot_supply_4c_phe(temperature):
    c = config()
    c["pH_inputs"]["pHe"].update(value=7.2, temperature_C=temperature, evidence="assay channel")
    assert "pHe_temperature_matched_observation_or_supported_model" in readiness(c)["missing"]


def test_nominally_filled_inventory_never_authorizes_fitting_or_free_prediction():
    c = config()
    c["concentration_basis"]["source_processing_verified"] = True
    for pool in c["accessible_pools"].values():
        pool.update(free_fraction=1, aqueous_fraction=1, recovery_fraction=1, activity_coefficient=1, evidence="synthetic test")
    for ph in ("pHi", "pHe"):
        c["pH_inputs"][ph].update(value=7.2, temperature_C=4, evidence="synthetic test")
    c["buffering"].update(beta_i_mM_per_L_cells_per_pH=65, beta_e_mM_per_L_supernatant_per_pH=10,
                          temperature_C=4, evidence="synthetic test", representation="effective_total_capacity")
    for section in ("buffering", "kinetics"):
        for key in c[section]:
            if key.endswith("_contract"):
                c[section][key] = "synthetic test"
    r = readiness(c)
    assert r["prerequisite_inventory_complete"]
    assert not r["free_pH_prediction_authorized"] and not r["optimization_authorized"]
    c["pH_inputs"]["pHi"]["compartment"] = "extracellular"
    assert "pHi_temperature_matched_observation_or_supported_model" in readiness(c)["missing"]
