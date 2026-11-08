"""JBC observations stay exact, separate and disabled for production training."""

import csv
import json
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from fla_jbc_data import (SCHEDULES, SHEET_CHANNEL_COUNTS, channel_mapping,
                          numeric_value, read_workbook, schedule)
from ingest_jbc_supplements import (CONFIG, model_coverage, run, source_conflicts,
                                   summarize, validate_design, verify)


@pytest.fixture
def synthetic_workbook(tmp_path):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, count in SHEET_CHANNEL_COUNTS.items():
        sheet = workbook.create_sheet(name)
        sheet.append([None, "time"] + [f"synthetic{i} ({'exo' if name == 'exo' else 'endo'})" for i in range(count)])
        sheet.append(["units", "days"] + ["mM"] * count)
        for temperature in SCHEDULES:
            for replicate in range(3):
                for index, day in enumerate(schedule(name, temperature)):
                    sheet.append([f"{temperature} degrees C" if replicate == 0 and index == 0 else None,
                                  day] + [float(replicate+index+1)] * count)
            sheet.append([None] * (count+2))
    path = tmp_path / "synthetic.xlsx"
    workbook.save(path)
    return workbook, path


def test_complete_schedules_and_source_slots(synthetic_workbook):
    _, path = synthetic_workbook
    channels, samples, observations = read_workbook(path)
    assert len(channels) == 96 and len(samples) == 372 and len(observations) == 11886
    assert all(not row["training_enabled"] for row in observations)
    assert all(not row["cross_sheet_pairing_verified"] and row["donor_id"] == "" for row in samples)
    assert all(row["storage_day_from_documented_origin"] == row["source_day"] + 1 for row in samples)


def test_missing_and_zero_are_distinct(synthetic_workbook):
    workbook, path = synthetic_workbook
    workbook["endo"]["C3"] = None
    workbook["endo"]["D3"] = 0
    workbook.save(path)
    _, _, observations = read_workbook(path)
    assert observations[0]["value"] is None and observations[0]["is_missing"]
    assert observations[1]["value"] == 0 and observations[1]["is_zero"]


@pytest.mark.parametrize("value", [True, float("inf"), float("nan"), "0.1", "=1+1"])
def test_invalid_numeric_not_repaired(value):
    with pytest.raises(ValueError):
        numeric_value(value, "endo!C3")


@pytest.mark.parametrize("cell,value", [("C3", -1), ("C3", "=1+1"), ("C3", True),
                                       ("B4", 0), ("B4", -1), ("B4", None), ("A3", 5)])
def test_invalid_sheet_data_rejected(synthetic_workbook, cell, value):
    workbook, path = synthetic_workbook
    workbook["endo"][cell] = value
    workbook.save(path)
    with pytest.raises(ValueError):
        read_workbook(path)


def test_homonymous_channels_keep_distinct_column_ids(synthetic_workbook):
    workbook, path = synthetic_workbook
    workbook["assay"]["E1"] = workbook["assay"]["R1"] = "hemoglobin concentration"
    workbook.save(path)
    channels, _, _ = read_workbook(path)
    duplicate = [c for c in channels if c["duplicate_label"]]
    assert {c["channel_id"] for c in duplicate} == {"assay!E", "assay!R"}


@pytest.mark.parametrize("label,sheet,unit,expected", [
    ("6-phosphogluconate (endo)", "endo", "mM", "GO6P"),
    ("D-glucose (exo)", "assay", "mM", "EGLC"),
    ("L-lactate (exo)", "assay", "mM", "ELAC"),
    ("nicotinamide (endo)", "endo", "mM", ""),
    ("S-adenosylmethioninamine (endo)", "endo", "mM", ""),
    ("5-methylthioadenosine (endo)", "endo", "mM", ""),
    ("LDH activity", "assay", "U/L", ""),
    ("pH", "assay", "units", ""),
    ("L-glycerate (endo)", "endo", "mM", ""),
])
def test_conservative_pool_mapping(label, sheet, unit, expected):
    mapping = channel_mapping(label, sheet, unit)
    assert mapping["candidate_model_pools"] == expected
    assert not mapping["training_enabled"] and not mapping["volume_basis_verified"]


def test_pooled_phosphoglycerate_never_split():
    mapping = channel_mapping("phosphoglycerate pool (endo)", "endo", "mM")
    assert mapping["candidate_operator"] == "P2G + P3G"
    assert "do_not_split" in mapping["mapping_status"]


@pytest.mark.parametrize("label", ["ATP (endo)", "glucose-6-phosphate (endo)"])
def test_conflicting_pool_definitions_hold_mapping(label):
    assert channel_mapping(label, "endo", "mM")["mapping_status"].startswith("hold_")


def test_37C_assay_only_extension():
    assert schedule("assay", 37)[-1] == 14
    assert schedule("endo", 37)[-1] == schedule("exo", 37)[-1] == 7
    assert schedule("endo", 4)[1] == 1.0417


def test_summary_is_descriptive_not_covariance(synthetic_workbook):
    _, path = synthetic_workbook
    _, _, observations = read_workbook(path)
    summary = summarize(observations)
    assert all(row["n_reported"] == 3 for row in summary)
    assert all(row["covariance_or_accuracy_limit"] == "not_estimated" for row in summary)


@pytest.mark.parametrize("flag", ["ode_execution_allowed", "kinetic_optimization_allowed",
                                 "initial_state_changes_allowed", "volume_conversion_allowed",
                                 "automatic_teacher_generation_allowed", "production_training_enabled"])
def test_no_fit_or_conversion_authorized(flag):
    design = json.loads(CONFIG.read_text())
    design[flag] = True
    with pytest.raises(ValueError):
        validate_design(design)


def test_all_conflicts_are_explicit():
    conflicts = {item["id"] for item in source_conflicts()}
    assert {"ATP_compartment", "DPG_not_measured", "hexose_6_phosphate_identity",
            "volume_denominator", "replicate_identity", "not_flux_or_redox"} <= conflicts


def test_real_source_roundtrip_and_no_redox_measurement(tmp_path):
    design = json.loads(CONFIG.read_text())
    if not Path(design["workbook"]).exists() or not (ROOT / design["parent_archive"]).exists():
        pytest.skip("local supplied source and sealed preparation required")
    out = tmp_path / "archive"
    summary = run(out, design)
    assert summary["observations_total"] == 11886 and summary["zero"] == 182
    assert summary["missing"] == summary["negative_concentrations"] == 0
    assert verify(out)["independent_source_cell_checks"] == 11886
    channels, _, _ = read_workbook(design["workbook"])
    coverage = model_coverage(channels, ROOT / "src/equadiff_brodbar.py")
    assert len(coverage) == 113
    assert all(row["coverage"] == "unobserved_in_JBC" for row in coverage
               if row["model_pool"] in {"NAD", "NADH", "NADP", "NADPH", "B13PG", "B23PG"})
    with pytest.raises(ValueError, match="fresh"):
        run(out, design)
    with (out / "observations_long.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["value"] = "999"
    with (out / "observations_long.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="output changed"):
        verify(out)
