"""Strict Vmax-only (fixed Km) contract: pure tests, no solver, no calibration core.

Written on 2026-11-12 and NOT executed by their author.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.services import vmax_only_contract as contract


def classify(name):
    """Stand-in for the core classifier, including one Vmax name that is also regulation."""
    classes = set()
    if name.startswith("vmax_"):
        classes.add("vmax")
    if name.startswith("km_") or name.startswith("hybrid_km_"):
        classes.add("km")
    if name.startswith("hybrid_"):
        classes.add("hybrid")
    if name.startswith(("ki_", "ka_", "alpha_", "n_")) or name == "vmax_VREGULATED":
        classes.add("regulation")
    return classes


def request(**fields):
    base = {"optimization_strategy": None, "method": None, "parameter_contract": None}
    base.update(fields)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("fields, requested_by", [
    ({"optimization_strategy": "vmax_only"}, ["optimization_strategy"]),
    ({"method": " VMAX_ONLY "}, ["method"]),
    ({"optimization_strategy": "vmax_only", "method": "vmax_only"}, ["method", "optimization_strategy"]),
    ({"parameter_contract": "vmax_only_fixed_km"}, ["parameter_contract"]),
    ({"parameter_contract": "vmax_only", "method": "vmax_only"}, ["parameter_contract", "method"]),
])
def test_fixed_km_is_selected_by_contract_or_by_either_strategy_field(fields, requested_by):
    decision = contract.resolve_parameter_contract(request(**fields))
    assert decision["fixed_km"] is True and decision["contract"] == contract.FIXED_KM_CONTRACT
    assert decision["strategy"] == "vmax_only" and decision["requested_by"] == requested_by


@pytest.mark.parametrize("fields", [
    {},
    {"optimization_strategy": "vmax_then_km"},
    {"method": "joint_vmax_km"},
    {"parameter_contract": "legacy_unconstrained", "optimization_strategy": "km_only"},
    {"parameter_contract": "legacy"},
])
def test_historical_path_is_identified_and_left_alone(fields):
    decision = contract.resolve_parameter_contract(request(**fields))
    assert decision == {"contract": contract.LEGACY_CONTRACT, "fixed_km": False, "requested_by": [], "strategy": None}


@pytest.mark.parametrize("fields", [
    {"optimization_strategy": "vmax_only", "method": "km_only"},
    {"optimization_strategy": "joint_vmax_km", "method": "vmax_only"},
    {"parameter_contract": "vmax_only_fixed_km", "optimization_strategy": "vmax_then_km"},
    {"parameter_contract": "vmax_only_fixed_km", "method": "staged_full"},
    {"parameter_contract": "legacy_unconstrained", "optimization_strategy": "vmax_only"},
    {"parameter_contract": "legacy", "method": "vmax_only"},
    {"parameter_contract": "km_free"},
])
def test_conflicting_or_unknown_requests_are_refused_not_resolved_by_precedence(fields):
    with pytest.raises(contract.StrategyConflict):
        contract.resolve_parameter_contract(request(**fields))


def test_object_without_the_new_field_still_resolves():
    assert contract.resolve_parameter_contract(SimpleNamespace(optimization_strategy="vmax_only"))["fixed_km"]
    assert not contract.resolve_parameter_contract(SimpleNamespace())["fixed_km"]


@pytest.mark.parametrize("name, expected", [
    ("vmax_VHK", True),
    ("vmax_VAK_rev", True),
    ("km_ATP", False),
    ("ki_ATP_PK", False),
    ("ka_F16BP", False),
    ("alpha_PFK", False),
    ("n_PFK", False),
    ("hybrid_blend_VPK", False),
    ("hybrid_km_VPK", False),
    ("vmax_VREGULATED", False),
    ("", False),
    ("VMAX_VHK", False),
])
def test_only_pure_vmax_names_are_allowed(name, expected):
    assert contract.is_vmax_only_parameter(name, classify) is expected


def test_prefix_rule_alone_applies_without_a_classifier():
    assert contract.is_vmax_only_parameter("vmax_VREGULATED") is True
    assert contract.is_vmax_only_parameter("km_ATP") is False


def test_caller_selection_with_any_non_vmax_name_is_refused_and_names_are_listed():
    assert contract.require_vmax_only_selection(["vmax_VHK", "vmax_VPK", "vmax_VHK"], classify, origin="x") == ["vmax_VHK", "vmax_VPK"]
    with pytest.raises(contract.FixedKmViolation) as error:
        contract.require_vmax_only_selection(["vmax_VHK", "km_ATP", "ki_ATP_PK"], classify, origin="params_to_optimize")
    assert "km_ATP" in str(error.value) and "ki_ATP_PK" in str(error.value) and "params_to_optimize" in str(error.value)


def test_derived_parameters_keep_vmax_and_report_everything_else():
    kept, dropped = contract.filter_derived_parameters(
        ["vmax_VHK", "km_GLC", "ki_ATP_PK", "vmax_VPK", "hybrid_blend_VPK", "vmax_VREGULATED"], classify)
    assert kept == ["vmax_VHK", "vmax_VPK"]
    assert dropped == ["km_GLC", "ki_ATP_PK", "hybrid_blend_VPK", "vmax_VREGULATED"]
    assert contract.filter_derived_parameters([], classify) == ([], [])


def test_stage_plan_must_be_explicit_and_vmax_only():
    good = [{"name": "vmax_only", "parameter_classes": ["vmax"], "include_params": ["vmax_VHK", "vmax_VPK"]}]
    contract.assert_stage_plan_vmax_only(good, classify)
    for bad in ([],
                [{"name": "s", "parameter_classes": ["vmax"], "include_params": []}],
                [{"name": "s", "parameter_classes": ["vmax"]}],
                [{"name": "s", "parameter_classes": ["vmax"], "include_params": ["vmax_VHK", "km_ATP"]}],
                [{"name": "s", "parameter_classes": ["vmax", "km"], "include_params": ["vmax_VHK"]}],
                [good[0], {"name": "km_stage", "parameter_classes": ["km"], "include_params": ["km_ATP"]}],
                [{"name": "legacy", "include_params": ["vmax_VHK", "ki_ATP_PK"]}]):
        with pytest.raises(contract.FixedKmViolation):
            contract.assert_stage_plan_vmax_only(bad, classify)


def test_audit_passes_only_when_everything_outside_the_optimised_set_is_bit_identical():
    before = {"vmax_VHK": 1.0, "vmax_VPK": 2.0, "km_ATP": 0.5, "ki_ATP_PK": 1.7}
    after = {"vmax_VHK": 1.3, "vmax_VPK": 2.0, "km_ATP": 0.5, "ki_ATP_PK": 1.7}
    audit = contract.audit_fixed_parameters(before, after, ["vmax_VHK"], classify)
    assert audit["verified"] and audit["checked"] == 3
    assert audit["changed_non_vmax"] == {} and audit["changed_unselected_vmax"] == {}


def test_audit_reports_a_changed_km_with_no_tolerance():
    before = {"vmax_VHK": 1.0, "km_ATP": 0.5}
    after = {"vmax_VHK": 1.3, "km_ATP": 0.5000000001}
    audit = contract.audit_fixed_parameters(before, after, ["vmax_VHK"], classify)
    assert not audit["verified"] and audit["changed_non_vmax"] == {"km_ATP": [0.5, 0.5000000001]}


def test_audit_separates_unselected_vmax_changes_missing_references_and_bad_selections():
    before = {"vmax_VHK": 1.0, "vmax_VPK": 2.0, "km_ATP": 0.5}
    after = {"vmax_VHK": 1.3, "vmax_VPK": 2.5, "km_ATP": 0.5, "km_NEW": 1.0, "purine_structure_mode": "legacy"}
    audit = contract.audit_fixed_parameters(before, after, ["vmax_VHK"], classify)
    assert not audit["verified"]
    assert audit["changed_unselected_vmax"] == {"vmax_VPK": [2.0, 2.5]} and audit["changed_non_vmax"] == {}
    assert audit["without_reference"] == ["km_NEW"]
    audit = contract.audit_fixed_parameters(before, {"vmax_VHK": 1.0, "km_ATP": 0.9}, ["km_ATP"], classify)
    assert not audit["verified"] and audit["non_vmax_in_optimized_set"] == ["km_ATP"]


def test_fixed_km_request_is_a_copy_with_both_fields_set_and_memory_off():
    original = SimpleNamespace(optimization_strategy=None, method="vmax_only", parameter_contract=None,
                               enable_strategy_memory=True, params_to_optimize={"vmax_VHK": [1, 0, 2]})
    snapshot = dict(vars(original))
    copy = contract.fixed_km_request(original)
    assert vars(original) == snapshot and copy is not original
    assert copy.optimization_strategy == copy.method == "vmax_only"
    assert copy.parameter_contract == contract.FIXED_KM_CONTRACT and copy.enable_strategy_memory is False
    assert copy.params_to_optimize == {"vmax_VHK": [1, 0, 2]}
