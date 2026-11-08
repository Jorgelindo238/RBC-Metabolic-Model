"""Single-reaction replacement, bit-identical reference and full flux closure."""

import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rbc_glut_only_transport import equadiff_glut_only
from rbc_distinct_volume_transport import equadiff_distinct_volume, glut_import, phase_matrix


def state():
    x = np.r_[np.full(113, .2), 7.2]
    x[0], x[85] = 1.2, 25.
    return x


def kinetics():
    return {"conductance": .027, "km_i": 3.49, "km_e": 23.5}


def evaluate(x, **kw):
    audit = {}
    derivative = equadiff_glut_only(1, x, hematocrit=.58, numerical_audit=audit, **kw)
    return derivative, audit


def test_no_override_preserves_archived_reference_bitwise():
    x = state()
    a, audit = evaluate(x)
    other = {}
    b = equadiff_distinct_volume(1, x, mode="phase_native", hematocrit=.58,
                                ph_policy="clamped_diagnostic", numerical_audit=other)
    np.testing.assert_array_equal(a, b)
    assert audit["raw_fluxes"] == other["raw_fluxes"]
    assert audit["effective_fluxes"] == other["effective_fluxes"]


@pytest.mark.parametrize("policy", ["initial", "reverse", "zero_import", "zero_export"])
def test_only_VEGLC_changes_and_amount_balance_closes(policy):
    x = state()
    if policy == "reverse":
        x[0], x[85] = 25, 1
    if policy == "zero_import":
        x[0] = 0
    if policy == "zero_export":
        x[85] = 0
    before = x.copy()
    base, b = evaluate(x)
    d, a = evaluate(x, glucose_kinetics=kinetics())
    names, reactions, matrix, volumes, _ = phase_matrix(.58)
    for r in reactions:
        if r != "VEGLC":
            assert a["raw_fluxes"][r] == b["raw_fluxes"][r]
            assert a["effective_fluxes"][r] == b["effective_fluxes"][r]
    expected = glut_import(x[0], x[85], **kinetics())
    assert a["raw_fluxes"]["VEGLC"] == expected
    v = np.array([a["effective_fluxes"][r] for r in reactions])
    np.testing.assert_allclose(d[:113], matrix @ v, atol=1e-12, rtol=1e-12)
    delta = d-base
    assert volumes[0]*delta[0]+volumes[85]*delta[85] == pytest.approx(0, abs=1e-12)
    assert d[-1] == base[-1] == 0
    np.testing.assert_array_equal(x, before)
    assert a["GLC_is_predicted_state"] and not a["MCT_activated"]
    if policy == "zero_import":
        assert d[0] >= 0
    if policy == "zero_export":
        assert d[85] >= 0


@pytest.mark.parametrize("kw", [{"positivity_policy": "legacy"}, {"curve_fit_strength": .1},
    {"ph_policy": "native"}, {"glucose_kinetics": {"conductance": .1}},
    {"glucose_kinetics": {"conductance": -.1, "km_i": 1, "km_e": 1}}])
def test_incomplete_or_forced_scope_rejected(kw):
    options = {"glucose_kinetics": kinetics(), **kw}
    with pytest.raises(ValueError):
        evaluate(state(), **options)


def test_source_candidate_matches_the_verified_real_fit():
    candidate = json.loads((ROOT / "config/fla_glucose_real_candidate.json").read_text())
    path = ROOT / candidate["source_archive"] / "summary.json"
    fit = next(f for f in json.loads(path.read_text())["selected_by_training_only"] if f["case"] == candidate["source_case"])
    assert fit["numerical_pass"] and fit["optimizer_success"]
    row = next(r for r in fit["conditional_geometry_candidates"] if r["hematocrit"] == candidate["working_hematocrit"])
    assert row["GLUT_conductance_cell_basis"] == candidate["glucose_kinetics"]["conductance"]
    assert candidate["planned_override_reactions"] == ["VEGLC"]
