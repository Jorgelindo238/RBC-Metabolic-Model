"""Read source cells and pinned GEM transports; never rescale training data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import urllib.request

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fla_transport_observation_contract.json"
DEFAULT_OUT = ROOT / "output/fla_transport_contract_2026_10_06_v3"
INGESTION = ROOT / "output/jbc_supplements_ingestion_2026_10_06"
NETWORK = ROOT / "output/rbc_gem_network_audit_2026_10_06"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def positive(value, name):
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def amount_transport_derivatives(q_export, ci, ce, vi, ve, dvi=0.0, dve=0.0):
    """Pure dimensional audit: Q mmol/day, C mmol/L, V L; no ODE integration."""
    positive(vi, "vi")
    positive(ve, "ve")
    if any(isinstance(v, bool) or not math.isfinite(v) for v in (q_export, ci, ce, dvi, dve)):
        raise ValueError("finite numeric values required")
    if min(ci, ce) < 0:
        raise ValueError("negative concentration")
    return (-q_export - ci * dvi) / vi, (q_export - ce * dve) / ve


def phase_to_bag(ci, ce, hematocrit):
    """Constant unit-volume geometry, not a conversion of experimental records."""
    if isinstance(hematocrit, bool) or not math.isfinite(hematocrit) or not 0 < hematocrit < 1:
        raise ValueError("hematocrit must be strictly between zero and one")
    if any(isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in (ci, ce)):
        raise ValueError("finite nonnegative concentrations required")
    return hematocrit * ci, (1 - hematocrit) * ce


def inspect_gem(path):
    model = read_json(path)
    result = []
    for r in model["reactions"]:
        s = r["metabolites"]
        lactate = "lac__L_c" in s and "lac__L_e" in s
        if not lactate and r["id"] not in ("GLC_Dt", "EX_glc__D_e", "EX_lac__L_e"):
            continue
        result.append({
            "id": r["id"], "name": r["name"], "stoichiometry": s,
            "lower_bound": r["lower_bound"], "upper_bound": r["upper_bound"],
            "gene_reaction_rule": r["gene_reaction_rule"],
            "references": r.get("annotation", {}).get("references", []),
            "lactate_transport": lactate,
            "positive_flux_lactate_direction": (
                "export" if s.get("lac__L_e", 0) > 0 else "import"
            ) if lactate else None,
        })
    return sorted(result, key=lambda r: r["id"])


def read_csv_tsv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def comparable_transports(records):
    # Version1.2 uses semicolon-separated references;1.3 uses JSON arrays.
    result = []
    for record in records:
        item = dict(record)
        references = item["references"]
        item["references"] = references.split(";") if isinstance(references, str) else references
        result.append(item)
    return result


def inspect_jbc(config):
    path = ROOT / config["jbc_workbook"]
    if sha(path) != config["jbc_workbook_sha256"]:
        raise ValueError("JBC source hash mismatch")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        selected = []
        seen = set()
        source_tables = {name: list(wb[name].values) for name in wb.sheetnames}
        for r in read_csv(INGESTION / "observations_long.csv"):
            if r["channel_id"] not in config["jbc_channels"] or r["is_missing"] == "True":
                continue
            key = r["sheet"], r["source_cell"]
            if key in seen:
                raise ValueError("duplicate source-cell record")
            seen.add(key)
            row = int(r["excel_row"])
            col = openpyxl.utils.column_index_from_string(r["channel_id"].split("!")[1])
            values = source_tables[r["sheet"]]
            if values[row - 1][col - 1] != float(r["value"]):
                raise ValueError(f"source value mismatch {key}")
            if values[0][col - 1] != r["exact_source_label"] or values[1][col - 1] != r["source_unit"]:
                raise ValueError(f"source header/unit mismatch {key}")
            if r["donor_id"] or r["cross_sheet_pairing_verified"] != "False":
                raise ValueError("unexpected asserted donor linkage; re-audit the contract")
            if r["source_volume_conversion_applied"] != "False" or r["training_enabled"] != "False":
                raise ValueError("source extraction unexpectedly rescaled or training enabled")
            if r["channel_id"] == "assay!D":
                if r["source_unit"] != "L/L" or not 0 < float(r["value"]) < 1:
                    raise ValueError("invalid source hematocrit")
            selected.append({**r, "role": config["jbc_channels"][r["channel_id"]]})
        stats = []
        for channel in config["jbc_channels"]:
            for temperature in sorted({r["temperature_C"] for r in selected}, key=float):
                rows = [r for r in selected if r["channel_id"] == channel and r["temperature_C"] == temperature]
                if not rows:
                    continue
                values = [float(r["value"]) for r in rows]
                stats.append({"channel_id": channel, "temperature_C": float(temperature),
                              "source_unit": rows[0]["source_unit"], "n": len(rows),
                              "minimum": min(values), "maximum": max(values)})
        return selected, stats
    finally:
        wb.close()


def inspect_sheet1():
    wb = openpyxl.load_workbook(ROOT / "src/Data_Bordbar_et_al_exp.xlsx", read_only=True, data_only=True)
    try:
        rows = list(wb["Sheet1"].values)
        channels = []
        for index, row in enumerate(rows[1:], 2):
            if row[0] in ("GLC", "EGLC", "LAC", "ELAC"):
                channels.append({"channel": row[0], "excel_row": index, "j1_cell": f"B{index}",
                                 "values": list(row[1:]), "denominator_verified": False})
        if len(channels) != 4:
            raise ValueError("expected four distinct local glucose/lactate rows")
        return {"header": rows[0][0], "reported_days": list(rows[0][1:]), "channels": channels,
                "donor_linkage_verified": False, "rescaling_applied": False}
    finally:
        wb.close()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_config(config):
    if type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise ValueError("invalid schema")
    for key in ("production_enabled", "normalization_enabled", "optimization_enabled"):
        if config.get(key) is not False:
            raise ValueError("source audit cannot authorize production changes")


def verify(out):
    manifest = read_json(out / "manifest.json")
    for base, key in ((ROOT, "input_sha256"), (out, "output_sha256")):
        for relative, expected in manifest[key].items():
            path = (base / relative).resolve()
            if not path.is_relative_to(base.resolve()) or sha(path) != expected:
                raise ValueError(f"archive hash mismatch {relative}")
    config = read_json(out / "contract.json")
    validate_config(config)
    selected, stats = inspect_jbc(config)
    if selected != read_csv(out / "jbc_selected_source_cells.csv") or stats != read_json(out / "jbc_channel_statistics.json"):
        raise ValueError("JBC source reconstruction mismatch")
    for version in config["gem_versions"]:
        base = NETWORK / "github" / version
        if inspect_gem(base / "model/RBC-GEM.json") != read_json(out / f"gem_{version}_transports.json"):
            raise ValueError("GEM reconstruction mismatch")
    curated = read_json(out / "gem_1.3.0_curated_transport_evidence.json")
    target_ids = {r["id"] for r in read_json(out / "gem_1.3.0_transports.json")}
    expected = {"version": "1.3.0", "rows": [r for r in read_csv_tsv(
        NETWORK / "github/1.3.0/data/curation/reactions_evidence.tsv") if r["reactions"] in target_ids]}
    if curated != expected:
        raise ValueError("curated evidence reconstruction mismatch")
    if inspect_sheet1() != read_json(out / "local_sheet1_transport_rows.json"):
        raise ValueError("local source reconstruction mismatch")
    return {"verified": True, "input_hashes": len(manifest["input_sha256"]),
            "output_hashes": len(manifest["output_sha256"]), "source_cells_reconstructed": len(selected)}


def build(out, fetch_methods=False):
    config = read_json(CONFIG)
    validate_config(config)
    inputs = [CONFIG, Path(__file__), ROOT / "qa/test_rbc_transport_contract.py",
              ROOT / "tasks/fla_transport_contract_2026_10_06.md",
              ROOT / config["jbc_workbook"], INGESTION / "observations_long.csv", INGESTION / "pdf_evidence.json",
              ROOT / "src/Data_Bordbar_et_al_exp.xlsx", ROOT / "src/equadiff_brodbar.py",
              ROOT / "src/extracellular_teacher_flux.py", ROOT / "RBC/Rxn_RBC.txt",
              ROOT / "config/fla_working_reference.json", ROOT / "output/fla_common_manifest_2026_10_06/manifest.json"]
    for version in config["gem_versions"]:
        base = NETWORK / "github" / version
        inputs.append(base / "model/RBC-GEM.json")
    curation_path = NETWORK / "github/1.3.0/data/curation/reactions_evidence.tsv"
    inputs.append(curation_path)
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in inputs}
    out.mkdir(parents=True, exist_ok=False)
    selected, stats = inspect_jbc(config)
    write_json(out / "contract.json", config)
    write_csv(out / "jbc_selected_source_cells.csv", selected)
    write_json(out / "jbc_channel_statistics.json", stats)
    write_json(out / "local_sheet1_transport_rows.json", inspect_sheet1())
    models = {}
    for version in config["gem_versions"]:
        base = NETWORK / "github" / version
        models[version] = inspect_gem(base / "model/RBC-GEM.json")
        write_json(out / f"gem_{version}_transports.json", models[version])
    if comparable_transports(models["1.2.0"]) != comparable_transports(models["1.3.0"]):
        raise ValueError("transport evidence differs between GEM versions; review before continuing")
    target_ids = {r["id"] for r in models["1.3.0"]}
    write_json(out / "gem_1.3.0_curated_transport_evidence.json", {
        "version": "1.3.0", "rows": [r for r in read_csv_tsv(curation_path) if r["reactions"] in target_ids]
    })
    summary = {"purpose": config["purpose"], "selected_source_cells": len(selected),
               "hematocrit_values": sum(r["channel_id"] == "assay!D" for r in selected),
               "lactate_routes": sum(r["lactate_transport"] for r in models["1.3.0"]),
               "gem_target_transport_evidence_equal_after_reference_encoding_normalization": True,
               "raw_reference_encoding_differences": sum(a != b for a, b in zip(models["1.2.0"], models["1.3.0"])),
               "source_normalization_applied": False, "donor_split_created": False,
               "production_changed": False, "ode_or_optimization_run": False}
    if fetch_methods:
        source = next(r for r in config["primary_sources"] if r["id"] == "ufba2017")
        request = urllib.request.Request(source["accessible_pdf"], headers={"User-Agent": "AIRBC source audit"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(10_000_001)
        if len(data) > 10_000_000 or not data.startswith(b"%PDF"):
            raise ValueError("methods retrieval did not return a bounded PDF")
        (out / "ufba2017_primary_methods.pdf").write_bytes(data)
        from pypdf import PdfReader
        pages = PdfReader(out / "ufba2017_primary_methods.pdf").pages
        hits = [i + 1 for i, page in enumerate(pages) if "total bag volume" in " ".join(page.extract_text().split())]
        if not hits:
            raise ValueError("published normalization statement not found in retrieved PDF")
        summary["ufba_normalization_pdf_pages"] = hits
    write_json(out / "summary.json", summary)
    for relative, expected in hashes.items():
        if sha(ROOT / relative) != expected:
            raise ValueError(f"protected input changed {relative}")
    outputs = {str(p.relative_to(out)).replace("\\", "/"): sha(p) for p in sorted(out.iterdir()) if p.is_file()}
    write_json(out / "manifest.json", {"input_sha256": hashes, "output_sha256": outputs})
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--fetch-methods", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.verify) if args.verify else build(args.out, args.fetch_methods), indent=2))
