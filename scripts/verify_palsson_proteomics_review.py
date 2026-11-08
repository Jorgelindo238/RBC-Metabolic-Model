"""Verify the sealed source review without altering its parent manifests."""

import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "output/palsson_proteomics_review_2026_10_06"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    checks = 0
    for folder in (ARCHIVE, ARCHIVE / "evidence_extension_v2"):
        manifest = json.loads((folder / "manifest.json").read_text())
        for path, expected in manifest["input_sha256"].items():
            assert digest(Path(path)) == expected, path
            checks += 1
        for name, expected in manifest["output_sha256"].items():
            assert digest(folder / name) == expected, name
            checks += 1

    with (ARCHIVE / "human_protein_copy_numbers.csv").open(newline="") as stream:
        records = list(csv.DictReader(stream))
    assert len(records) == 3799
    assert len({row["uniprot_id"] for row in records}) == 3799
    source = ARCHIVE / "source_files/Supplementary Table 1 - FINAL.xlsx"
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        rows = {index: row for index, row in enumerate(
            workbook["Sheet1"].iter_rows(values_only=True), start=1
        )}
        for record in records:
            row = rows[int(record["source_row"])]
            assert str(row[0]).split("|")[1] == record["uniprot_id"]
            assert ("" if row[3] is None else str(row[3])) == record["gene"]
            assert float(row[5]) == float(record["copy_number_per_cell_F"])
            assert float(row[6]) == float(record["multi_anchor_copy_number_per_cell_G"])
            checks += 4
    finally:
        workbook.close()

    junit = ARCHIVE / "proteomics_qa_results.xml"
    suites = ET.parse(junit).getroot()
    cases = suites.findall(".//testcase")
    assert len(cases) == 24
    assert not suites.findall(".//failure")
    assert not suites.findall(".//error")
    assert not suites.findall(".//skipped")
    paths = [
        Path(__file__).resolve(),
        ROOT / "qa/test_palsson_proteomics_review.py",
        ROOT / "qa/test_palsson_source_metadata.py",
        ROOT / "tasks/fla_proteomics_source_review_2026_10_06.md",
        ROOT / "tasks/fla_current_tasks.md",
        ROOT / "fla_progress_log.md",
        junit,
        ARCHIVE / "manifest.json",
        ARCHIVE / "evidence_extension_v2/manifest.json",
    ]
    receipt = {
        "manifest_and_source_value_checks_passed": checks,
        "human_protein_rows_reconstructed": len(records),
        "targeted_tests_passed": len(cases),
        "full_qa_rerun": False,
        "model_or_initial_conditions_changed": False,
        "optimization_executed": False,
        "sha256": {str(path): digest(path) for path in paths},
        "scope": "Source-value reconstruction and parent/extension hashes; not biological validation.",
    }
    target = ARCHIVE / "final_verification.json"
    if target.exists():
        assert json.loads(target.read_text()) == receipt, "Existing receipt differs"
    else:
        target.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
