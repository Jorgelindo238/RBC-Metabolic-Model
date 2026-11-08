"""Independently compare every exported S6 value/key with its workbook cell."""

import csv
import hashlib
import json
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "output/rbc_gem_network_audit_2026_10_06"
EXPORT = BASE / "priority_proteomics_v2"
SOURCE = ROOT / "output/palsson_proteomics_review_2026_10_06/retrieved_sources/pcbi.1012109.s008.xlsx"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, description):
    if not condition:
        raise ValueError(description)


def main():
    destination = BASE / "source_value_verification.json"
    require(not destination.exists(), "Verification receipt already exists")
    manifest = json.loads((EXPORT / "manifest.json").read_text())
    for path, expected in manifest["input_sha256"].items():
        require(sha(Path(path)) == expected, f"Input hash mismatch: {path}")
    for name, expected in manifest["output_sha256"].items():
        require(sha(EXPORT / name) == expected, f"Output hash mismatch: {name}")
    workbook = load_workbook(SOURCE, read_only=True, data_only=True)
    results = {}
    try:
        for sheet_name, unit in (("Table D", "nmol protein / gDW sample"),
                                 ("Table E", "copies/cell")):
            path = EXPORT / f"{sheet_name.replace(' ', '_')}_priority_observations.csv"
            with path.open(newline="") as stream:
                records = list(csv.DictReader(stream))
            cells = {(int(row["source_row"]), int(row["source_column"])): row for row in records}
            require(len(cells) == len(records), "Duplicate exported source coordinates")
            selected_rows = {coordinate[0] for coordinate in cells}
            iterator = workbook[sheet_name].iter_rows(values_only=True)
            header = next(iterator)
            checked = zeros = missing = 0
            for source_row, row in enumerate(iterator, 2):
                if source_row not in selected_rows:
                    continue
                for column, value in enumerate(row[1:], 2):
                    record = cells.pop((source_row, column))
                    label = header[column - 1]
                    donor, day = label.rsplit("_D", 1)
                    require(record["sheet"] == sheet_name and record["uniprot"] == row[0],
                            "Source row identity mismatch")
                    require(record["sample_id"] == label and record["donor_id"] == donor
                            and int(record["storage_day"]) == int(day), "Sample identity mismatch")
                    require(record["reported_unit"] == unit, "Source unit mismatch")
                    require(record["training_enabled"] == "False"
                            and record["estimated_abundance"] == "True", "Export policy mismatch")
                    require(record["missing"] == str(value is None), "Missingness mismatch")
                    require(record["reported_value"] == "" if value is None
                            else float(record["reported_value"]) == value, "Source value mismatch")
                    checked += 1
                    zeros += value == 0
                    missing += value is None
            require(not cells, "Exported coordinates absent from source")
            require(checked == 114576, "Unexpected verification count")
            results[sheet_name] = {"source_values_checked": checked, "reported_zero": zeros,
                                   "missing": missing, "selected_proteins": len(selected_rows)}
        with (EXPORT / "donor_metadata.csv").open(newline="") as stream:
            exported = list(csv.reader(stream))
        original = workbook["Table F"].iter_rows(values_only=True)
        require(exported[0] == ["source_sheet_row", *next(original)], "Donor header mismatch")
        donor_cells = 0
        for index, source_row in enumerate(original, 2):
            expected = [str(index), *("" if value is None else str(value) for value in source_row)]
            require(exported[index - 1] == expected, f"Donor metadata mismatch at row {index}")
            donor_cells += len(source_row)
        require(index == len(exported) == 617, "Donor row count mismatch")
        results["Table F"] = {"donors_checked": 616, "source_cells_checked": donor_cells}
    finally:
        workbook.close()
    receipt = {"all_passed": True, "checks": results, "source_sha256": sha(SOURCE),
               "verifier_sha256": sha(Path(__file__).resolve()),
               "export_manifest_sha256": sha(EXPORT / "manifest.json"),
               "method": "Workbook cells reopened independently; exact numeric/key comparison, no tolerance"}
    destination.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
