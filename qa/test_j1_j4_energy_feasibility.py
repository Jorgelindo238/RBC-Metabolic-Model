from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_j1_j4_energy_feasibility import REACTIONS, screen, solve


def panel():
    names = ["ATP", "ADP", "AMP", "B13PG", "P3G", "GTP", "GDP", "PRPP", "R5P"]
    matrix = np.array([[1,-1,-1], [-1,1,0], [0,0,1], [-1,0,0], [1,0,0],
                       [0,1,0], [0,-1,0], [0,0,1], [0,0,-1]], float)
    x = np.tile(np.array([.1, .04, 1., .02, .5, 1., 1., .1, 1.])[:, None], (1,4))
    target = {"ATP": 1., "ADP": 1., "AMP": .4, "P3G": .5}
    return matrix, x, names, list(REACTIONS), np.ones((3,3)), target, {p: .1 for p in target}, {"working_MSE_allowance_fraction": .01}


def test_dual_certificate_for_capped_flux():
    x, proof = solve(np.array([-1.]), np.array([[1.]]), np.array([.5]), [(0., 2.)])
    assert x[0] == .5 and proof["dual_objective"] == -.5


def test_combined_stock_bound_even_without_raw_ceiling():
    cases, bounds = screen(*panel())
    assert bounds["J4_H_upper_mM"] == pytest.approx(.24)
    assert cases["combined_no_PGK_raw_ceiling"]["maximum_H_stock_only"]["J4_H_mM"] == pytest.approx(.24)
    assert cases["PGK_raw_envelope"]["maximum_H_stock_only"]["J4_H_mM"] == pytest.approx(.13)
    assert cases["combined_raw_envelope"]["maximum_H_stock_only"]["minimum_endpoint_stock_mM"] >= -1e-8


def test_adp_obstruction_survives_all_scenarios():
    cases, bounds = screen(*panel())
    assert bounds["ADP_band_multiplier_lower_bound"] == pytest.approx(9.6)
    assert all(v["minimum_joint_band_multiplier"] >= 9.6-1e-8 for v in cases.values())
    assert not any(v["fits_unit_working_bands"] for v in cases.values())


def test_zero_PGK_raw_headroom_does_not_create_flux():
    args = panel()
    args[4][:, 0] = 0.
    cases, _ = screen(*args)
    assert cases["PGK_raw_envelope"]["maximum_H_guarded"]["J4_H_mM"] == cases["fixed"]["maximum_H_guarded"]["J4_H_mM"]
