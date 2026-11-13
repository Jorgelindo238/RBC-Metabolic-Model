"""User calibration data contract and preflight: pure tests, no solver, no calibration core.

Written on 2026-11-12 and NOT executed by their author.
"""

from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.services import user_data_contract as contract

SCHEMA = json.loads((ROOT / "config/user_calibration_data_schema_v1.json").read_text(encoding="utf-8"))


def valid_payload():
    return {
        "schema_version": contract.SCHEMA_VERSION,
        "dataset": {"dataset_id": "lab-a-2026-01", "label": "Lab A storage series", "cohort_id": "lab-a",
                    "subject": {"kind": "donor", "id": "donor-07"}},
        "time": {"unit": "day", "origin": {"kind": "collection", "description": "day 0 is the day of collection"},
                 "points": [1.0, 4.0, 8.0, 15.0]},
        "geometry": {"hematocrit": 0.6, "provenance": {"kind": "measured_this_dataset", "source": "unit record"}},
        "initial_state": {"policy": "user_measured_at_first_time", "time": 1.0,
                          "unmeasured_pools_policy": "declared_latent_contract",
                          "latent_contract": "config/fla_latent_inventory_contract_2026_11_12.json"},
        "channels": [
            {"name": "ATP", "compartment": "intracellular", "kind": "absolute", "unit": "mM", "values": [1.0, 1.1, 1.2, 1.0]},
            {"name": "GLC", "compartment": "extracellular", "kind": "absolute", "unit": "mM", "values": [25.0, 24.0, None, 20.0]},
        ],
    }


def codes(report, key="errors"):
    return [issue["code"] for issue in report[key]]


def blocking(report):
    return [issue["code"] for issue in report["engine_compatibility"]["blocking"]]


def test_schema_file_and_module_carry_the_same_version_and_vocabularies():
    assert SCHEMA["$id"] == contract.SCHEMA_VERSION == SCHEMA["properties"]["schema_version"]["const"]
    channel = SCHEMA["properties"]["channels"]["items"]["properties"]
    assert tuple(channel["compartment"]["enum"]) == contract.COMPARTMENTS
    assert tuple(channel["kind"]["enum"]) == contract.CHANNEL_KINDS
    initial = SCHEMA["properties"]["initial_state"]["properties"]
    assert tuple(initial["policy"]["enum"]) == contract.INITIAL_STATE_POLICIES
    assert not set(initial["policy"]["enum"]) & set(contract.FORBIDDEN_INITIAL_STATE_POLICIES)
    assert tuple(SCHEMA["properties"]["geometry"]["properties"]["provenance"]["properties"]["kind"]["enum"]) == contract.GEOMETRY_PROVENANCE


def test_valid_dataset_is_valid_but_the_engine_is_not_compatible_and_nothing_is_launched():
    report = contract.preflight(valid_payload())
    assert report["data_valid"] is True and report["errors"] == []
    assert report["engine_compatibility"]["compatible"] is False
    assert report["launch_allowed"] is False
    assert {"engine_initial_state_ignores_user_data", "engine_no_compartment_volumes",
            "engine_time_origin_not_bound"} <= set(blocking(report))
    assert "data_invalid" not in blocking(report)
    assert report["conversions_performed"] == [] and report["donors_merged"] is False
    assert report["initial_state_substituted"] is False
    assert report["dataset_identity"] == {"dataset_id": "lab-a-2026-01", "cohort_id": "lab-a",
                                         "subject_kind": "donor", "subject_id": "donor-07"}


def test_preflight_does_not_modify_its_input():
    payload = valid_payload()
    snapshot = deepcopy(payload)
    contract.preflight(payload)
    assert payload == snapshot


@pytest.mark.parametrize("payload", [None, [], "text", 3])
def test_non_object_payload_is_reported_not_raised(payload):
    report = contract.preflight(payload)
    assert not report["data_valid"] and "payload_not_an_object" in codes(report)
    assert report["launch_allowed"] is False and "data_invalid" in blocking(report)


@pytest.mark.parametrize("version", [None, "airbc.user_calibration_data/2", 1])
def test_unknown_schema_version_is_refused(version):
    payload = valid_payload(); payload["schema_version"] = version
    assert "schema_version_unsupported" in codes(contract.preflight(payload))


@pytest.mark.parametrize("change, code", [
    (lambda p: p.pop("dataset"), "dataset_missing"),
    (lambda p: p["dataset"].update(dataset_id=" "), "dataset_identity_missing"),
    (lambda p: p["dataset"].pop("cohort_id"), "dataset_identity_missing"),
    (lambda p: p["dataset"]["subject"].update(kind="pool"), "subject_kind_invalid"),
    (lambda p: p["dataset"]["subject"].pop("id"), "subject_id_missing"),
    (lambda p: p["dataset"].update(subjects=[{"id": "a"}, {"id": "b"}]), "multiple_subjects_in_one_payload"),
    (lambda p: p["dataset"].update(donors=["a", "b"]), "multiple_subjects_in_one_payload"),
    (lambda p: p["dataset"]["subject"].update(kind="declared_group"), "group_definition_missing"),
    (lambda p: p["dataset"]["subject"].update(kind="declared_group", group_definition={"description": "pool", "pooling_method": "mean"}),
     "group_size_missing"),
])
def test_identity_of_dataset_cohort_and_donor_or_declared_group_is_required(change, code):
    payload = valid_payload(); change(payload)
    report = contract.preflight(payload)
    assert code in codes(report) and not report["data_valid"]


def test_a_declared_group_is_accepted_only_when_fully_declared():
    payload = valid_payload()
    payload["dataset"]["subject"] = {"kind": "declared_group", "id": "pool-3",
                                     "group_definition": {"description": "three donors", "pooling_method": "arithmetic mean", "n_subjects": 3}}
    report = contract.preflight(payload)
    assert report["data_valid"] and report["donors_merged"] is False
    assert report["dataset_identity"]["subject_kind"] == "declared_group"


@pytest.mark.parametrize("points, code", [
    ([], "time_points_missing"),
    ([1.0, float("nan"), 8.0, 15.0], "time_points_not_finite"),
    ([1.0, float("inf"), 8.0, 15.0], "time_points_not_finite"),
    ([1.0, "4", 8.0, 15.0], "time_points_not_finite"),
    ([1.0, 4.0, 4.0, 15.0], "time_points_not_increasing"),
    ([1.0, 8.0, 4.0, 15.0], "time_points_not_increasing"),
])
def test_times_must_be_finite_and_strictly_increasing(points, code):
    payload = valid_payload(); payload["time"]["points"] = points
    assert code in codes(contract.preflight(payload))


@pytest.mark.parametrize("change, code", [
    (lambda p: p["time"].update(unit="hour"), "time_unit_invalid"),
    (lambda p: p["time"].pop("origin"), "time_origin_missing"),
    (lambda p: p["time"]["origin"].update(description=""), "time_origin_undescribed"),
])
def test_time_unit_and_origin_are_explicit(change, code):
    payload = valid_payload(); change(payload)
    assert code in codes(contract.preflight(payload))


@pytest.mark.parametrize("values", [[1.0, 1.1, 1.2], [1.0, 1.1, 1.2, 1.0, 0.9], "1,2,3,4", None])
def test_series_must_align_with_the_time_points(values):
    payload = valid_payload(); payload["channels"][0]["values"] = values
    assert "channel_length_mismatch" in codes(contract.preflight(payload))


@pytest.mark.parametrize("values, code", [
    ([1.0, float("nan"), 1.2, 1.0], "channel_value_not_finite"),
    ([1.0, "1.1", 1.2, 1.0], "channel_value_not_finite"),
    ([1.0, -0.1, 1.2, 1.0], "channel_value_negative"),
    ([None, None, None, None], "channel_empty"),
])
def test_values_are_finite_non_negative_or_explicitly_missing(values, code):
    payload = valid_payload(); payload["channels"][0]["values"] = values
    assert code in codes(contract.preflight(payload))


@pytest.mark.parametrize("change, code", [
    (lambda c: c.pop("compartment"), "channel_compartment_missing"),
    (lambda c: c.update(compartment="plasma"), "channel_compartment_missing"),
    (lambda c: c.pop("kind"), "channel_kind_missing"),
    (lambda c: c.pop("unit"), "channel_unit_invalid"),
    (lambda c: c.update(unit="mg/dL"), "channel_unit_invalid"),
    (lambda c: c.update(name=""), "channel_name_missing"),
    (lambda c: c.update(anchor={"value": 1.0, "unit": "mM", "time": 1.0, "source": "x"}), "absolute_channel_with_relative_fields"),
])
def test_each_channel_declares_name_compartment_kind_and_unit(change, code):
    payload = valid_payload(); change(payload["channels"][0])
    assert code in codes(contract.preflight(payload))


def test_same_pool_in_two_compartments_is_two_channels_but_a_repeat_is_refused():
    payload = valid_payload()
    payload["channels"].append({"name": "GLC", "compartment": "intracellular", "kind": "absolute", "unit": "mM", "values": [1.1, 1.2, 1.2, 1.2]})
    assert contract.preflight(payload)["data_valid"]
    payload["channels"].append({"name": "glc", "compartment": "intracellular", "kind": "absolute", "unit": "mM", "values": [1.0, 1.0, 1.0, 1.0]})
    report = contract.preflight(payload)
    assert "channel_duplicated" in codes(report) and not report["data_valid"]


def relative_channel(**extra):
    channel = {"name": "IMP", "compartment": "intracellular", "kind": "relative", "unit": "fold_change",
               "values": [1.0, 1.4, 2.0, 2.6], "normalization": {"basis": "first_point", "description": "divided by day 1"}}
    channel.update(extra)
    return channel


def test_relative_series_without_anchor_is_valid_data_flagged_and_never_fittable_as_concentration():
    payload = valid_payload(); payload["channels"].append(relative_channel())
    report = contract.preflight(payload)
    assert report["data_valid"] and "relative_without_anchor" in codes(report, "warnings")
    assert "relative_without_anchor_not_fittable_as_concentration" in blocking(report)
    assert report["launch_allowed"] is False and report["conversions_performed"] == []
    assert report["channels"][2] == {"name": "IMP", "compartment": "intracellular", "kind": "relative",
                                     "unit": "fold_change", "anchored": False, "observed": 4}


def test_relative_series_with_a_sourced_anchor_is_still_not_converted_and_still_blocked():
    payload = valid_payload()
    payload["channels"].append(relative_channel(anchor={"value": 0.12, "unit": "mM", "time": 1.0, "source": "enzymatic assay, same unit"}))
    report = contract.preflight(payload)
    assert report["data_valid"] and report["channels"][2]["anchored"] is True
    assert "engine_no_relative_observation_model" in blocking(report)
    assert "relative_without_anchor" not in codes(report, "warnings")
    assert report["conversions_performed"] == [] and report["launch_allowed"] is False


@pytest.mark.parametrize("change, code", [
    (lambda c: c.update(unit="mM"), "relative_channel_with_absolute_unit"),
    (lambda c: c.pop("normalization"), "relative_normalization_missing"),
    (lambda c: c["normalization"].update(description=""), "relative_normalization_missing"),
    (lambda c: c.update(anchor={"value": 0.12, "unit": "mM", "time": 1.0}), "relative_anchor_invalid"),
    (lambda c: c.update(anchor={"value": 0.0, "unit": "mM", "time": 1.0, "source": "x"}), "relative_anchor_invalid"),
    (lambda c: c.update(anchor={"value": 0.12, "unit": "fold_change", "time": 1.0, "source": "x"}), "relative_anchor_invalid"),
])
def test_relative_channels_need_a_relative_unit_a_normalization_and_a_sourced_anchor_if_any(change, code):
    payload = valid_payload(); channel = relative_channel(); change(channel); payload["channels"].append(channel)
    report = contract.preflight(payload)
    assert code in codes(report) and not report["data_valid"]


def test_scaling_a_relative_series_changes_no_verdict_and_scaling_an_absolute_one_is_not_normalized_away():
    payload = valid_payload(); payload["channels"].append(relative_channel())
    scaled = deepcopy(payload); scaled["channels"][2]["values"] = [10 * v for v in scaled["channels"][2]["values"]]
    first, second = contract.preflight(payload), contract.preflight(scaled)
    assert first["data_valid"] == second["data_valid"] and blocking(first) == blocking(second)
    assert first["channels"] == second["channels"]
    micromolar = valid_payload(); micromolar["channels"][0].update(unit="uM", values=[1000.0, 1100.0, 1200.0, 1000.0])
    report = contract.preflight(micromolar)
    assert report["data_valid"] and "engine_requires_mM_no_conversion_performed" in blocking(report)
    assert report["channels"][0]["unit"] == "uM" and report["conversions_performed"] == []


@pytest.mark.parametrize("change, code", [
    (lambda p: p["geometry"].pop("hematocrit"), "hematocrit_invalid"),
    (lambda p: p["geometry"].update(hematocrit=0.0), "hematocrit_invalid"),
    (lambda p: p["geometry"].update(hematocrit=1.0), "hematocrit_invalid"),
    (lambda p: p["geometry"].update(hematocrit=58), "hematocrit_invalid"),
    (lambda p: p["geometry"].pop("provenance"), "geometry_provenance_missing"),
    (lambda p: p["geometry"]["provenance"].update(source=""), "geometry_source_missing"),
])
def test_hematocrit_is_a_fraction_with_stated_provenance(change, code):
    payload = valid_payload(); change(payload)
    assert code in codes(contract.preflight(payload))


def test_borrowed_geometry_is_accepted_only_as_declared_borrowed():
    payload = valid_payload()
    payload["geometry"] = {"hematocrit": 0.58, "provenance": {"kind": "borrowed", "source": "working geometry, not this donor"}}
    assert contract.preflight(payload)["data_valid"]


@pytest.mark.parametrize("policy", ["bordbar_reference", "reference_dataset", "engine_default"])
def test_user_initial_state_is_never_replaced_by_a_reference_or_engine_default(policy):
    payload = valid_payload(); payload["initial_state"]["policy"] = policy
    report = contract.preflight(payload)
    assert "initial_state_replaced_by_reference" in codes(report) and not report["data_valid"]
    assert report["initial_state_substituted"] is False


@pytest.mark.parametrize("change, code", [
    (lambda s: s.update(policy="fitted"), "initial_state_policy_invalid"),
    (lambda s: s.pop("time"), "initial_state_time_missing"),
    (lambda s: s.update(time=0.0), "initial_state_time_mismatch"),
    (lambda s: s.update(time=4.0), "initial_state_time_mismatch"),
    (lambda s: s.pop("unmeasured_pools_policy"), "unmeasured_pools_policy_missing"),
    (lambda s: s.update(policy="user_declared_table"), "initial_state_table_missing"),
    (lambda s: s.update(policy="user_declared_table", values=[{"name": "ATP", "compartment": "intracellular", "unit": "mM", "value": 1.0}]),
     "initial_state_entry_invalid"),
])
def test_initial_state_contract_sits_at_the_first_time_point_without_back_extrapolation(change, code):
    payload = valid_payload(); change(payload["initial_state"])
    assert code in codes(contract.preflight(payload))


def test_undeclared_unmeasured_pools_are_a_warning_not_a_silent_default():
    payload = valid_payload(); payload["initial_state"]["unmeasured_pools_policy"] = "undeclared"
    report = contract.preflight(payload)
    assert report["data_valid"] and "unmeasured_pools_undeclared" in codes(report, "warnings")


def test_identical_series_are_flagged_without_calling_them_aliases():
    payload = valid_payload()
    payload["channels"].append({"name": "B13PG", "compartment": "intracellular", "kind": "absolute", "unit": "mM", "values": [3.5, 3.0, 2.0, 0.6]})
    payload["channels"].append({"name": "B23PG", "compartment": "intracellular", "kind": "absolute", "unit": "mM", "values": [3.5, 3.0, 2.0, 0.6]})
    report = contract.preflight(payload)
    assert report["data_valid"]
    flagged = [issue for issue in report["warnings"] if issue["code"] == "identical_series"]
    assert len(flagged) == 1 and "may not be independent" in flagged[0]["message"] and "alias" not in flagged[0]["message"]


def test_engine_blocking_reasons_are_reported_even_for_the_simplest_valid_dataset():
    payload = valid_payload(); payload["channels"] = payload["channels"][:1]
    report = contract.preflight(payload)
    assert report["data_valid"] and blocking(report) == [
        "engine_initial_state_ignores_user_data", "engine_no_compartment_volumes", "engine_time_origin_not_bound"]
    assert report["engine_compatibility"]["engine"] == contract.ENGINE_NAME


def test_legacy_notice_states_its_limits():
    notice = contract.legacy_path_notice()
    assert notice["status"] == "legacy_no_data_contract" and notice["schema_version"] is None
    assert len(notice["limits"]) == len(contract.LEGACY_PATH_LIMITS) >= 5
    assert any("initial state" in limit for limit in notice["limits"])
    assert any("relative" in limit for limit in notice["limits"])
