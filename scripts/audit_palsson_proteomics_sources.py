"""Read-only protein/HTML source audit and bounded primary-source retrieval."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

CONFIG = ROOT / "config/fla_proteomics_source_review.json"
DEFAULT_OUT = ROOT / "output/palsson_proteomics_review_2026_10_06"
FILES = ["Supplementary Table 1 - FINAL.xlsx", "index.html", "RBC Proteome 2025.html",
         "Interactome 2025.html", "Phosphoproteomics 2025.html", "Cysteine Oxidation 2025.html"]
GENES_TO_REACTIONS = {
    "HK1": "VHK", "GPI": "VPGI", "PFKL": "VPFK", "PFKM": "VPFK", "PFKP": "VPFK",
    "ALDOA": "VFDPA", "TPI1": "VTPI", "GAPDH": "VGAPDH", "PGK1": "VPGK",
    "BPGM": "VDPGM|V23DPGP", "PGAM1": "VPGM", "PGAM2": "VPGM", "ENO1": "VENOPGM",
    "PKLR": "VPK", "PKM": "VPK", "LDHA": "VLDH", "LDHB": "VLDH",
    "G6PD": "VG6PDH", "PGLS": "VPGLS", "PGD": "V6PGD", "RPIA": "VR5PI", "RPE": "VR5PE",
    "TKT": "VTKL1|VTKL2", "TALDO1": "VTAL", "AK1": "VAK_forward_reverse_capacities", "NME1": "VNDPK", "NME2": "VNDPK",
    "GSR": "VGSR", "GCLC": "VGLUCYS", "GCLM": "VGLUCYS_regulatory_subunit", "GSS": "VGSS",
    "GPX1": "VGPX", "GPX4": "requires_substrate_specific_mapping", "PRDX2": "redox_network_audit_only",
    "CAT": "H2O2_clearance_network_audit_only", "CYB5R3": "redox_network_audit_only", "SLC2A1": "VEGLC", "SLC16A1": "VELAC_candidate",
    "ATP1A1": "NaK_ATPase_not_explicit_current_reaction", "ATP1B1": "NaK_ATPase_not_explicit_current_reaction",
    "AMPD3": "VAMPD1_candidate_isoform_name_mismatch", "APRT": "VAPRT", "HPRT1": "VHGPRT1|VHGPRT2",
    "PRPS1": "VPRPPASe_candidate", "PRPS2": "VPRPPASe_candidate", "ADA": "VADA", "NT5C2": "purine_network_audit_only",
    "BLVRB": "not_an_explicit_current_reaction", "SLC4A1": "binding_scaffold_not_explicit_current_state",
    "PCMT1": "protein_repair_not_explicit_current_reaction",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_frozen_reference():
    archive = ROOT / "output/jbc_supplements_ingestion_2026_10_06"
    contract = json.loads((archive / "preregistered_contract.json").read_text())
    final = json.loads((archive / "final_verification.json").read_text())
    substitutions = []
    for path, expected in contract["input_sha256"].items():
        actual = Path(path)
        if not actual.exists():
            replacement = archive / "source_files" / actual.name
            if actual.name not in {"jbc.M117.804914-1.xlsx", "jbc.M117.804914-2.pdf"} or not replacement.exists():
                raise ValueError("missing frozen non-source input: " + path)
            substitutions.append({"missing_original": path, "identical_archived_copy": str(replacement)})
            actual = replacement
        if sha(actual) != expected:
            raise ValueError("frozen input changed: " + path)
    for path, expected in final["output_sha256"].items():
        if sha(archive / path) != expected:
            raise ValueError("JBC archive output changed: " + path)
    return {"JBC_outputs_and_registered_local_inputs_unchanged": True,
            "archived_source_copy_substitutions": substitutions,
            "original_external_inputs_all_available": not substitutions}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        raise ValueError("cannot export an empty evidence table")
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class TableReader(HTMLParser):
    """Ignore scripts; preserve duplicate headers and source row positions."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.table, self.row, self.cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.table is not None:
                raise ValueError("nested tables require a distinct parser")
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append("\n")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def parse_table(content):
    reader = TableReader()
    reader.feed(content)
    if len(reader.tables) != 1:
        raise ValueError("one explicit source table required")
    headers, *rows = reader.tables[0]
    if not headers or any(len(row) != len(headers) for row in rows):
        raise ValueError("source HTML table is not rectangular")
    return headers, rows


def parse_plotly(content):
    position = content.rfind("Plotly.newPlot(")
    if position < 0:
        raise ValueError("no Plotly source call found")
    remaining = content[position + len("Plotly.newPlot("):].lstrip()
    decoder = json.JSONDecoder()
    values = []
    for _ in range(3):
        value, end = decoder.raw_decode(remaining)
        values.append(value)
        remaining = remaining[end:].lstrip()
        if remaining.startswith(","):
            remaining = remaining[1:].lstrip()
    if not isinstance(values[0], str) or not isinstance(values[1], list) or not isinstance(values[2], dict):
        raise ValueError("unexpected Plotly data/layout types")
    json.dumps(values, allow_nan=False)
    return {"plot_id": values[0], "data": values[1], "layout": values[2], "javascript_executed": False}


def workbook_inventory(path):
    workbook = load_workbook(path, read_only=True, data_only=False)
    inventory, proteins, targets = [], [], []
    try:
        for sheet in workbook:
            nonempty, formulas = 0, 0
            for row in sheet.iter_rows():
                nonempty += sum(cell.value is not None for cell in row)
                formulas += sum(cell.data_type == "f" for cell in row)
            title = sheet.cell(1, 2).value if sheet.max_column > 1 else None
            inventory.append({"sheet": sheet.title, "max_row": sheet.max_row, "max_column": sheet.max_column,
                              "nonempty_cells": nonempty, "formula_cells": formulas,
                              "exact_sheet_description": str(title or ""), "training_enabled": False})
        sheet = workbook["Sheet1"]
        headers = list(next(sheet.iter_rows(min_row=2, max_row=2, values_only=True)))
        if headers[3] != "Gene" or headers[5:7] != ["Copy number/cell", "Protein copy number per cell (multi-anchor)"]:
            raise ValueError("original copy-number and gene headers required")
        for row_number, row in enumerate(sheet.iter_rows(min_row=3, values_only=True), start=3):
            if not isinstance(row[0], str) or not row[0].startswith("sp|"):
                continue
            item = {"sheet": "Sheet1", "source_row": row_number, "uniprot_id": row[1],
                    "gene": row[3], "description": row[4], "copy_number_per_cell_F": row[5],
                    "multi_anchor_copy_number_per_cell_G": row[6], "correction_factor_S": row[18],
                    "copy_number_is_complex_count": False, "active_fraction_measured": False,
                    "donor_variance_available_in_this_row": False, "training_enabled": False}
            for value in (row[5], row[6]):
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError("invalid reported copy number; do not repair")
            proteins.append(item)
            if row[3] in GENES_TO_REACTIONS:
                targets.append({**item, "candidate_reaction_annotation": GENES_TO_REACTIONS[row[3]],
                                "reaction_mapping_verified": False,
                                "multi_over_F": row[6] / row[5] if row[5] else None})
        if not proteins or not targets:
            raise ValueError("no protein evidence recovered")
    finally:
        workbook.close()
    return inventory, proteins, targets


def fetch(url, destination, limit=5_000_000):
    receipt = {"url": url, "destination": str(destination), "success": False}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "airbc-source-review/1.0"})
        with urllib.request.urlopen(request, timeout=35) as response:
            blob = response.read(limit+1)
            receipt.update(status=response.status, content_type=response.headers.get("Content-Type"), final_url=response.url)
        if len(blob) > limit:
            raise ValueError("bounded source download exceeded size limit")
        destination.write_bytes(blob)
        receipt.update(success=True, bytes=len(blob), sha256=sha(destination))
    except Exception as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
    return receipt


def verify(out):
    manifest = json.loads((out / "manifest.json").read_text())
    for path, expected in manifest["input_sha256"].items():
        if sha(path) != expected:
            raise ValueError("review input changed: " + path)
    for path, expected in manifest["output_sha256"].items():
        if sha(out / path) != expected:
            raise ValueError("review output changed: " + path)
    reference = verify_frozen_reference()
    return {"all_review_hashes_pass": True, **reference,
            "model_and_reference_unchanged": True, "proteomic_priors_activated": False}


def run(out, fetch_rbc_gem=False):
    if out.exists():
        raise ValueError("fresh review archive required")
    reference = verify_frozen_reference()
    design = json.loads(CONFIG.read_text())
    source = Path(design["local_source_directory"])
    inventory, proteins, targets = workbook_inventory(source / FILES[0])
    parsed, html_inventory = {}, []
    for name in FILES[2:]:
        content = (source / name).read_text(encoding="utf-8")
        if name.startswith("Interactome"):
            data = parse_plotly(content)
            parsed[name] = data
            html_inventory.append({"file": name, "kind": "Plotly_network_not_flux_measurements",
                                   "data_rows_or_traces": len(data["data"]), "headers": []})
        else:
            headers, rows = parse_table(content)
            parsed[name] = (headers, rows)
            html_inventory.append({"file": name, "kind": "source_table", "data_rows_or_traces": len(rows), "headers": headers})
    out.mkdir(parents=True)
    (out / "source_files").mkdir()
    (out / "retrieved_sources").mkdir()
    for name in FILES:
        shutil.copyfile(source / name, out / "source_files" / name)
    write_json(out / "source_review_config.json", design)
    write_json(out / "frozen_reference_check.json", reference)
    write_csv(out / "workbook_inventory.csv", inventory)
    write_csv(out / "human_protein_copy_numbers.csv", proteins)
    write_csv(out / "FLA_candidate_protein_map.csv", targets)
    write_json(out / "html_inventory.json", html_inventory)
    for name, data in parsed.items():
        stem = Path(name).stem.replace(" ", "_")
        if isinstance(data, dict):
            write_json(out / (stem + "_data.json"), data)
        else:
            headers, rows = data
            write_csv(out / (stem + "_table.csv"), [{"source_html_row": i+2,
                      **{f"column_{j+1}": value for j, value in enumerate(row)}} for i, row in enumerate(rows)])
    query = 'AUTH_LAST_NAME:Palsson AND (TITLE_ABS:"red blood" OR TITLE_ABS:erythrocyte) AND FIRST_PDATE:[2023-01-01 TO 2026-10-06]'
    search_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&pageSize=100&query=" + quote(query)
    receipts = [fetch(search_url, out / "retrieved_sources/europepmc_search.json")]
    for pmc in ("PMC13283417", "PMC11925312", "PMC11374506", "PMC13084699"):
        receipts.append(fetch(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmc}/fullTextXML",
                              out / f"retrieved_sources/{pmc}.xml"))
    meta_path = out / "retrieved_sources/RBC_GEM_S6_figshare_metadata.json"
    receipt = fetch("https://api.figshare.com/v2/articles/28583740", meta_path)
    receipts.append(receipt)
    if fetch_rbc_gem and receipt["success"]:
        metadata = json.loads(meta_path.read_text())
        for item in metadata["files"]:
            if item["name"].endswith(".xlsx"):
                destination = out / "retrieved_sources" / item["name"]
                receipt = fetch(item["download_url"], destination, limit=90_000_000)
                if receipt["success"]:
                    try:
                        with zipfile.ZipFile(destination) as archive:
                            if archive.testzip() is not None or "xl/workbook.xml" not in archive.namelist():
                                raise ValueError("not a complete Excel source")
                        expected_md5 = item.get("computed_md5") or item.get("supplied_md5")
                        if expected_md5 and hashlib.md5(destination.read_bytes()).hexdigest() != expected_md5:
                            raise ValueError("Figshare checksum mismatch")
                        receipt.update(validated_excel=True, figshare_checksum_match=bool(expected_md5),
                                       numerical_cells_imported=False)
                    except Exception as error:
                        receipt.update(validated_excel=False, validation_error=str(error))
                receipts.append(receipt)
    write_json(out / "retrieval_receipts.json", receipts)
    write_json(out / "summary.json", {"workbook_sheets": len(inventory), "human_protein_rows": len(proteins),
               "unique_human_uniprot_ids": len({row["uniprot_id"] for row in proteins}),
               "FLA_candidate_protein_rows": len(targets), "html_inventory": html_inventory,
               "original_copy_number_calibrations_preserved": True, "priors_activated": False,
               "ode_runs": 0, "fitted_parameters": 0, "model_or_initial_state_changes": False})
    inputs = [source / name for name in FILES] + [CONFIG, Path(__file__), ROOT / "qa/test_palsson_proteomics_review.py",
              ROOT / "src/equadiff_brodbar.py", ROOT / "src/Data_Bordbar_et_al_exp.xlsx",
              ROOT / "config/fla_working_reference.json",
              ROOT / "output/jbc_supplements_ingestion_2026_10_06/final_verification.json"]
    inputs = [p for p in inputs if p.exists()]
    write_json(out / "manifest.json", {"input_sha256": {str(p.resolve()): sha(p) for p in inputs},
               "output_sha256": {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
               "biological_contract_changed": False})
    return verify(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--fetch-rbc-gem", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.verify) if args.verify else run(args.out, args.fetch_rbc_gem), indent=2))
