"""Exploratory energy responses preserve measured J1 and biological guard separation."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from fla_coupled_energy_protocol import GROUPS, build_sensitivity_plan
from run_exploratory_energy_sensitivity import CONFIG, measured_initialization, mixed_response, run, single_response, validate_design


@pytest.fixture
def design():
    return json.loads(CONFIG.read_text())


def test_authorized_only_for_conditional_exploration(design):
    assert validate_design(design) is design
    assert design["planned_case_count"] == 19 and design["planned_ODE_integration_count"] == 38


@pytest.mark.parametrize("key,value", [
    ("schema_version", True), ("purpose", "biological_calibration"),
    ("biological_optimization_allowed", True), ("global_model_promotion_allowed", True),
    ("historical_contract_changed", True), ("initial_conditions_fitted", True),
    ("teacher_forcing", True), ("observation_reset", True), ("output_clipping", True),
    ("historical_initialization_enabled", True), ("user_authorized_exploratory_execution", False),
    ("horizon_day", [1., 46.]), ("planned_ODE_integration_count", 2),
    ("unknown_optimizer", "new"), ("single_group_log_steps", [.5, 1.]),
])
def test_scope_changes_rejected(design, key, value):
    design[key] = value
    with pytest.raises(ValueError):
        validate_design(design)


def test_existing_output_never_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        run(out=tmp_path)


def test_measured_zero_and_b13pg_exact_unmeasured_redox_unchanged():
    names = ("ATP", "B13PG", "ECYS", "NAD", "NADH")
    frozen = np.array([1., .0001, 1e-6, 1., 1.])
    table = pd.DataFrame({"Conc / mM": ["ATP", "B13PG", "ECYS"], 1: [.93, 3.58, 0.], 4: [1.08, 3., .1]})
    actual, inventory = measured_initialization(frozen, names, table)
    np.testing.assert_array_equal(actual, [.93, 3.58, 0., 1., 1.])
    np.testing.assert_array_equal(frozen, [1., .0001, 1e-6, 1., 1.])
    assert inventory.set_index("pool").loc["B13PG", "independent_observation"] == False
    assert inventory.set_index("pool").loc["NAD", "source"] == "unchanged_frozen_unmeasured_pool"


@pytest.mark.parametrize("problem", ["duplicate", "negative", "nonfinite", "missing_state", "wrong_time"])
def test_invalid_measurements_not_repaired(problem):
    table = pd.DataFrame({"Conc / mM": ["ATP", "ADP"], 1: [1., 2.], 4: [2., 1.]})
    if problem == "duplicate":
        table.iloc[1, 0] = "ATP"
    elif problem == "negative":
        table.iloc[0, 1] = -1.
    elif problem == "nonfinite":
        table.iloc[0, 1] = np.nan
    elif problem == "missing_state":
        table.iloc[0, 0] = "unknown"
    else:
        table = table.rename(columns={1: 0})
    with pytest.raises(ValueError):
        measured_initialization(np.ones(3), ("ATP", "ADP", "NAD"), table)


@pytest.fixture
def plan():
    resolved = {name: 1. for members in GROUPS.values() for name in members}
    resolved["vmax_VHK"] = 5.
    return build_sensitivity_plan(resolved)


def polynomial_features(plan):
    def value(scales):
        a, b, c = [scales.get(group, 0.) for group in GROUPS]
        return np.array([1.+2*a+3*b+4*c+5*a*b+6*a*c+7*b*c, a*a+b*b+c*c])
    return {case["case_id"]: value(case["log_scales"]) for case in plan["cases"]}


@pytest.mark.parametrize("group,expected", [("investment", 2.), ("AK_capacity", 3.), ("GAPDH_PGK_capacity", 4.)])
@pytest.mark.parametrize("step", [.05, .10])
def test_single_stencil_orientation_and_boundary(plan, group, expected, step):
    response = single_response(plan, polynomial_features(plan), group, step)
    np.testing.assert_allclose(response, [expected, -step if group == "investment" else 0.], atol=1e-12)


@pytest.mark.parametrize("first,second,expected", [
    ("investment", "AK_capacity", 5.), ("investment", "GAPDH_PGK_capacity", 6.),
    ("AK_capacity", "GAPDH_PGK_capacity", 7.),
])
def test_mixed_one_sided_and_central_stencils(plan, first, second, expected):
    np.testing.assert_allclose(mixed_response(plan, polynomial_features(plan), first, second), [expected, 0.], atol=1e-12)


def test_original_prepared_biological_protocol_remains_blocked():
    protocol = json.loads((ROOT / "output/adenylate_redox_readiness_2026_10_05_v2/coupled_sensitivity_protocol.json").read_text())
    assert protocol["execution_authorized"] is False and protocol["simulations_executed"] == 0
    assert protocol["execution_requires_scientific_contract_complete"] is True
