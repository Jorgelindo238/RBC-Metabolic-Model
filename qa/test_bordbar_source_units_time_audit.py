"""The provenance diagnostic must not silently change scientific inputs."""

import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_bordbar_source_units_time import accept_spreadsheet, run, validate_design, workbook_evidence


@pytest.fixture
def design():
    return json.loads((ROOT / "config/fla_bordbar_source_audit.json").read_text())


def test_read_only_design(design):
    assert validate_design(design) is design


@pytest.mark.parametrize("key,value", [
    ("schema_version", True), ("schema_version", 2), ("purpose", "calibration"),
    ("apply_time_offset", True), ("apply_normalization", True), ("modify_readiness", True),
    ("simulations_authorized", True), ("optimization_authorized", True),
    ("apply_time_offset", None), ("apply_normalization", 0),
    ("workbook", "other.xlsx"), ("time_offset_hypothesis_day", True),
    ("time_offset_hypothesis_day", 0.), ("time_offset_hypothesis_day", float("nan")),
])
def test_mutations_rejected(design, key, value):
    design[key] = value
    with pytest.raises(ValueError):
        validate_design(design)


def test_existing_archive_rejected(tmp_path):
    with pytest.raises(FileExistsError):
        run(out=tmp_path)


@pytest.mark.parametrize("kind", ["xlsx", "xls", "csv"])
def test_http_success_html_not_an_excel_dataset(kind):
    assert not accept_spreadsheet(b"<!DOCTYPE html><html>Access page</html>", kind)


def test_xlsx_requires_workbook_part():
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("unrelated.txt", "not a workbook")
    assert not accept_spreadsheet(stream.getvalue(), "xlsx")
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
    assert accept_spreadsheet(stream.getvalue(), "xlsx")


def test_xls_format_gate_requires_ole_signature():
    assert accept_spreadsheet(bytes.fromhex("d0cf11e0a1b11ae1") + b"fixture", "xls")
    assert not accept_spreadsheet(b"PK pretend excel", "xls")


@pytest.fixture(scope="module")
def receipt():
    return workbook_evidence(ROOT / "src/Data_Bordbar_et_al_exp.xlsx")


def test_actual_training_values_are_complete_and_nonnegative(receipt):
    source, ledger, times, values = receipt
    assert values.shape == (55, 14) and len(ledger) == 55
    assert np.isfinite(values).all() and (values >= 0).all()
    assert times.tolist() == [1., 4., 8., 11., 15., 18., 22., 25., 29., 32., 36., 38., 43., 46.]
    assert source["elapsed_span_days"] == 45.
    assert all(not row["volume_basis_verified"] and not row["upstream_row_mapping_verified"] for row in ledger)


def test_cellbb_is_bound_to_coefficient_sheet_not_concentration_sheet(receipt):
    source = receipt[0]
    metadata = source["metadata"]
    assert metadata["query_bindings"] == [{"sheet": "Feuil1", "query_part": "xl/queryTables/queryTable1.xml",
                                           "query_name": "cellbb", "connection_id": "1"}]
    table = metadata["cellbb_coefficient_table"]
    assert table["coefficient_row_count"] == 44
    assert table["headers"][1:] == ["b_1", "b_2", "b_3", "b_4", "b_5"]
    assert "LN(H$5)" in table["formula_example"]
    assert next(s for s in source["sheets"] if s["name"] == "Sheet1")["formula_count"] == 0


def test_duplicates_remain_declared_non_independent(receipt):
    pairs = {frozenset(pair.values()) for pair in receipt[0]["exact_duplicate_pairs"]}
    assert frozenset(("B13PG", "B23PG")) in pairs
    assert frozenset(("P2G", "P3G")) in pairs


def test_diagnostic_origin_does_not_relabel_irregular_time(receipt):
    times = receipt[2]
    hypothesis = times - 1.
    assert times[-4:].tolist() == [36., 38., 43., 46.]
    assert hypothesis[-4:].tolist() == [35., 37., 42., 45.]
