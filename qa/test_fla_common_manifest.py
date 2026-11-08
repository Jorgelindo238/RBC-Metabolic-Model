"""Manifest policy, alias, compartment and source reconstruction safeguards."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("common_manifest", ROOT / "scripts/build_fla_common_manifest.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def config():
    return MODULE.read_json(MODULE.CONFIG)


@pytest.mark.parametrize("key", MODULE.POLICY_KEYS)
def test_inventory_never_authorizes_model_changes(config, key):
    config["policy"][key] = True
    with pytest.raises(ValueError, match="cannot authorize"):
        MODULE.validate_config(config)


def test_missing_policy_is_not_false(config):
    del config["policy"]["optimization_allowed"]
    with pytest.raises(ValueError):
        MODULE.validate_config(config)


def test_boolean_schema_rejected(config):
    config["schema_version"] = True
    with pytest.raises(ValueError):
        MODULE.validate_config(config)


def test_atlas_alias_cannot_be_added_as_an_independent_study(config):
    alias = copy.deepcopy(next(row for row in config["sources"] if row["source_id"] == "population_atlas2026"))
    alias["source_id"] = "atlas_pubmed_duplicate"
    config["sources"].append(alias)
    with pytest.raises(ValueError, match="aliases"):
        MODULE.validate_config(config)


def test_orphan_cohort_rejected(config):
    config["datasets"][0]["cohort_id"] = "invented"
    with pytest.raises(ValueError, match="orphan"):
        MODULE.validate_config(config)


def test_duplicate_dataset_id_rejected(config):
    config["datasets"].append(copy.deepcopy(config["datasets"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        MODULE.validate_config(config)


def test_source_path_escape_rejected(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        MODULE.resolve_inside(tmp_path, "../other.csv")


@pytest.mark.parametrize("value", ["nan", "inf", "-1", True])
def test_invalid_measurement_is_not_sanitized(value):
    with pytest.raises(ValueError):
        MODULE.finite_nonnegative(value)


def test_zero_preserved():
    assert MODULE.finite_nonnegative("0") == 0


def test_compartment_uses_catalogue_not_e_prefix():
    mapping, external = MODULE.model_identity(ROOT)
    assert "E4P" in mapping and "E4P" not in external
    assert "EGLC" in external and "ELAC" in external


@pytest.fixture(scope="module")
def built():
    config = MODULE.read_json(MODULE.CONFIG)
    return MODULE.build(config, ROOT)


def test_exact_source_coverage_and_no_new_training(built):
    rows, samples, summaries = built
    by_dataset = {row["dataset_id"]: row for row in summaries}
    assert by_dataset["local_bordbar_sheet1"]["channel_representations"] == 55
    assert by_dataset["local_bordbar_sheet1"]["numeric_values_represented"] == 770
    assert by_dataset["jbc_temperature"]["channel_representations"] == 96
    assert by_dataset["jbc_temperature"]["numeric_values_represented"] == 11886
    assert by_dataset["gem_s6_priority"]["numeric_values_represented"] == 229152
    assert by_dataset["gem_s6_priority"]["identified_donors"] == 616
    assert by_dataset["gem_s6_priority"]["sample_records"] == 1848
    assert by_dataset["deep_red_human"]["channel_representations"] == 3799 * 2
    assert by_dataset["deep_red_human"]["sample_records"] == 0
    assert by_dataset["population_atlas_metadata"]["numeric_values_represented"] == 0
    assert all(row["training_enabled"] is False and row["independent_validation_eligible"] is False for row in rows)
    assert len({row["sample_id"] for row in samples}) == len(samples)


def test_duplicate_pools_remain_visible(built):
    by_label = {row["source_label"]: row for row in built[0] if row["dataset_id"] == "local_bordbar_sheet1"}
    assert by_label["B13PG"]["duplicate_series_group"] == "B13PG|B23PG"
    assert by_label["P2G"]["duplicate_series_group"] == "P2G|P3G"


def test_jbc_no_fake_donor_and_separate_time_coordinate(built):
    samples = [row for row in built[1] if row["dataset_id"] == "jbc_temperature"]
    assert len(samples) == 372
    assert all(row["donor_id"] == "" and row["split_assignment"] == "not_assigned" for row in samples)
    assert all(float(row["storage_day"]) == pytest.approx(float(row["source_day"]) + 1) for row in samples)
    rows = [row for row in built[0] if row["dataset_id"] == "jbc_temperature"]
    assert sum(row["reported_zero_count"] for row in rows) == 182
    assert not any(row["candidate_operator"] == "B23PG" for row in rows)


def test_proteomic_alternatives_are_one_evidence_group(built):
    counts = {}
    for row in built[0]:
        if row["representation_group"]:
            counts[row["representation_group"]] = counts.get(row["representation_group"], 0) + 1
    assert len([key for key in counts if key.startswith("gem_s6::")]) == 62
    assert len([key for key in counts if key.startswith("deep_red::")]) == 3799
    assert set(counts.values()) == {2}


def test_bardyn_placeholders_and_exposure_not_independent(built):
    summaries = {row["dataset_id"]: row for row in built[2]}
    assert summaries["bardyn_control"]["excluded_placeholder_channels"] == 58
    assert summaries["bardyn_supplemented"]["excluded_placeholder_channels"] == 61
    rows = [row for row in built[0] if row["dataset_id"] == "michel"]
    assert all("not_pristine_holdout" in row["exposure"] for row in rows)


def test_existing_archive_not_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        MODULE.run(tmp_path)


def test_hash_verifier_rejects_output_mutation(tmp_path):
    (tmp_path / "data.csv").write_text("changed", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"input_sha256": {}, "output_sha256": {"data.csv": "0" * 64}}))
    with pytest.raises(ValueError, match="output changed"):
        MODULE.verify(tmp_path)


def test_seal_rejects_mutated_source(tmp_path):
    base = tmp_path / "archive"
    base.mkdir()
    (base / "source.csv").write_text("changed", encoding="utf-8")
    (base / "seal.json").write_text(json.dumps({"output_sha256": {"source.csv": "0" * 64}}))
    with pytest.raises(ValueError, match="upstream hash"):
        MODULE.verify_seals({"seals": [{"root": "archive", "receipt": "seal.json", "key": "output_sha256"}]}, tmp_path)


def test_report_does_not_claim_donor_splits(config, built):
    text = MODULE.make_report(config, built[2], 1)
    assert "No train/test partition is fabricated" in text
    assert "not declared pristine holdouts" in text
    assert "not full S6 proteome coverage" in text
