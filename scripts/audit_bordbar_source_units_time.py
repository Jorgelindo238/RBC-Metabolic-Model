"""Audit Bordbar evidence without changing data, historical contracts or model inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from fla_precalibration_readiness import evaluate_readiness
from run_fla_sparse_teacher_resolution import verify_archive_inputs
from run_fla_synthetic_recovery import file_hash, write_json

CONFIG = ROOT / "config/fla_bordbar_source_audit.json"
DEFAULT_OUT = ROOT / "output/bordbar_source_units_time_audit_2026_10_06"
PATHS = ["Data_Brodbar_et_al_exp.xlsx", "Data_Bordbar_et_al_exp.xlsx",
         "src/Data_Brodbar_et_al_exp.xlsx", "src/Data_Bordbar_et_al_exp.xlsx"]
EXCLUDED = {".git", "node_modules", "venv", ".venv", "__pycache__", ".pytest_cache"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def validate_design(design):
    if type(design.get("schema_version")) is not int or design["schema_version"] != 1:
        raise ValueError("source audit schema 1 required")
    if design.get("purpose") != "read_only_Bordbar_lineage_units_time_audit":
        raise ValueError("read-only source audit required")
    for key in ("apply_time_offset", "apply_normalization", "modify_readiness", "simulations_authorized", "optimization_authorized"):
        if design.get(key) is not False:
            raise ValueError(f"source audit cannot authorize {key}")
    offset = design.get("time_offset_hypothesis_day")
    if design.get("workbook") != "src/Data_Bordbar_et_al_exp.xlsx" or type(offset) not in (int, float) or offset != 1.:
        raise ValueError("fixed source and diagnostic offset required")
    return design


def workbook_evidence(path):
    workbook = load_workbook(path, read_only=True, data_only=False)
    frame = pd.read_excel(path, sheet_name="Sheet1", engine="openpyxl")
    if frame.columns[0] != "Conc / mM":
        raise ValueError("unexpected training sheet")
    labels = frame.iloc[:, 0].astype(str).str.strip().str.upper().tolist()
    times = np.asarray(frame.columns[1:], dtype=float)
    values = frame.iloc[:, 1:].to_numpy(dtype=float)
    if len(set(labels)) != len(labels) or not np.all(np.isfinite(times)) or not np.all(np.diff(times) > 0):
        raise ValueError("duplicate pool names or invalid time partition")
    if not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("nonfinite or negative training concentration")
    sheets = [{"name": s.title, "rows": s.max_row, "columns": s.max_column, "visibility": s.sheet_state,
               "formula_count": sum(c.data_type == "f" for r in s.iter_rows() for c in r)} for s in workbook]
    ledger = []
    for index, pool in enumerate(labels):
        row = index+2
        ledger.append({"pool": pool, "sheet": "Sheet1", "label_cell": f"A{row}",
                       "first_cell": f"B{row}", "last_cell": f"O{row}",
                       "J1_nominal_mM": float(values[index, 0]), "J4_nominal_mM": float(values[index, 1]),
                       "J46_nominal_mM": float(values[index, -1]), "missing_count": int(np.isnan(values[index]).sum()),
                       "negative_count": int((values[index] < 0).sum()),
                       "upstream_row_mapping_verified": False, "volume_basis_verified": False,
                       "aggregation_and_replicates_verified": False})
    duplicates = [{"left": a, "right": b} for i, a in enumerate(labels) for j, b in enumerate(labels)
                  if j > i and np.array_equal(values[i], values[j])]
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        defined = [{"name": n.get("name"), "localSheetId": n.get("localSheetId"), "range": n.text}
                   for n in root.findall("m:definedNames/m:definedName", ns)]
        connections = []
        if "xl/connections.xml" in archive.namelist():
            connections = [{"attributes": dict(n.attrib), "children": [dict(tag=c.tag.rsplit("}", 1)[-1], **c.attrib) for c in n]}
                           for n in ET.fromstring(archive.read("xl/connections.xml"))]
        bindings = []
        relns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        for i, sheet in enumerate(workbook, 1):
            relpath = f"xl/worksheets/_rels/sheet{i}.xml.rels"
            if relpath not in archive.namelist():
                continue
            for rel in ET.fromstring(archive.read(relpath)).findall("r:Relationship", relns):
                if rel.get("Type", "").endswith("/queryTable"):
                    target = "xl/" + rel.get("Target").removeprefix("../")
                    query = ET.fromstring(archive.read(target))
                    bindings.append({"sheet": sheet.title, "query_part": target,
                                     "query_name": query.get("name"), "connection_id": query.get("connectionId")})
        metadata = {"defined_names": defined, "connections": connections, "query_bindings": bindings,
                    "absolute_path_hints": [n.get("url") for n in root.iter() if n.tag.rsplit("}", 1)[-1] == "absPath"]}
    coefficient_sheet = workbook["Feuil1"]
    coefficients = []
    for row in coefficient_sheet.iter_rows(min_row=6, max_col=6):
        if row[0].value is not None:
            coefficients.append({"pool": str(row[0].value), "row": row[0].row,
                                 "coefficient_cells": [c.coordinate for c in row[1:]],
                                 "coefficients": [float(c.value) for c in row[1:]]})
    metadata["cellbb_coefficient_table"] = {"sheet": "Feuil1", "header_cells": ["A5", "B5", "C5", "D5", "E5", "F5"],
        "headers": [coefficient_sheet.cell(5, i).value for i in range(1, 7)], "coefficient_row_count": len(coefficients),
        "rows": coefficients, "formula_example": coefficient_sheet["H12"].value,
        "does_not_establish_Sheet1_measurement_lineage": True}
    props = workbook.properties
    metadata["properties"] = {"creator": props.creator, "last_modified_by": props.lastModifiedBy,
        "created": str(props.created), "modified": str(props.modified), "title": props.title, "description": props.description}
    workbook.close()
    return {"sha256": file_hash(path), "shape": [len(labels), len(times)], "labels": labels,
            "nominal_unit_label": str(frame.columns[0]), "model_days": times.tolist(), "elapsed_span_days": float(times[-1]-times[0]),
            "sheets": sheets, "metadata": metadata, "exact_duplicate_pairs": duplicates,
            "missing_concentration_count": int(np.isnan(values).sum()), "negative_concentration_count": int((values < 0).sum()),
            "all_concentrations_finite": bool(np.all(np.isfinite(values)))}, ledger, times, values


def history_evidence(times, labels, values):
    refs = git("log", "--all", "--format=%H", "--", *PATHS).decode().splitlines()
    rows = []
    for ref in dict.fromkeys(refs):
        paths = git("ls-tree", "-r", "--name-only", ref, "--", *PATHS).decode().splitlines()
        for path in paths:
            blob = git("show", f"{ref}:{path}")
            frame = pd.read_excel(BytesIO(blob), sheet_name="Sheet1", engine="openpyxl")
            old_times = np.asarray(frame.columns[1:], dtype=float)
            old_values = frame.iloc[:, 1:].to_numpy(dtype=float)
            old_labels = frame.iloc[:, 0].astype(str).str.strip().str.upper().tolist()
            rows.append({"commit": ref, "path": path, "blob_sha256": hashlib.sha256(blob).hexdigest(),
                "commit_metadata": git("show", "-s", "--format=%aI%x09%s", ref).decode().strip(),
                "days": old_times.tolist(), "same_time_headers_as_current": bool(np.array_equal(times, old_times)),
                "same_concentration_values_as_current": bool(np.array_equal(values, old_values)),
                "same_labels_as_current": old_labels == labels})
    return rows


def search_cellbb(root=ROOT):
    found, skipped, errors, visited = [], set(), [], 0

    def on_error(error):
        errors.append(str(error))

    for directory, dirs, files in root.walk(on_error=on_error):
        for name in list(dirs):
            if name in EXCLUDED:
                dirs.remove(name)
                skipped.add(name)
        visited += len(files)
        found.extend(str(directory / name) for name in files if "cellbb" in name.lower() or "cellb" in name.lower())
    tracked = git("log", "--all", "--name-only", "--format=", "--", "*cellbb*", "*cellb*").decode().splitlines()
    return {"scope": str(root.resolve()), "files_enumerated": visited, "excluded_directory_names": sorted(skipped),
            "matching_workspace_files": sorted(found), "matching_names_in_all_git_history": sorted(set(filter(None, tracked))),
            "enumeration_errors": errors, "entire_user_computer_or_external_path_searched": False}


def accept_spreadsheet(payload, kind):
    if kind == "xlsx":
        if not zipfile.is_zipfile(BytesIO(payload)):
            return False
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            return "xl/workbook.xml" in archive.namelist()
    return kind == "xls" and payload.startswith(bytes.fromhex("d0cf11e0a1b11ae1"))


def supplementary_receipt(candidate, out):
    receipt = dict(candidate, checked_at=datetime.now(timezone.utc).isoformat(), usable_spreadsheet=False)
    try:
        with urllib.request.urlopen(candidate["url"], timeout=30) as response:
            body = response.read()
            receipt.update(status=response.status, resolved_url=response.url, content_type=response.headers.get("Content-Type"),
                           byte_count=len(body), response_sha256=hashlib.sha256(body).hexdigest())
        usable = accept_spreadsheet(body, candidate["expected_format"])
        receipt["usable_spreadsheet"] = usable
        filename = f"supplement_{candidate['expected_format']}_response." + (candidate["expected_format"] if usable else "bin")
        (out / filename).write_bytes(body)
        receipt["local_response_file"] = filename
        receipt["interpretation"] = "format valid; source contents require separate mapping" if usable else "not spreadsheet evidence; HTTP 200 is insufficient"
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        receipt["access_error"] = str(error)
    return receipt


def run(config_path=CONFIG, out=DEFAULT_OUT, *, fetch_supplements=False):
    if out.exists():
        raise FileExistsError("fresh directory required; prior evidence is sealed")
    design = validate_design(json.loads(config_path.read_text()))
    workbook = ROOT / design["workbook"]
    working_path = ROOT / "config/fla_working_reference.json"
    working = json.loads(working_path.read_text())
    context = ROOT / working["fixed_context"]
    preserved = [config_path, Path(__file__), workbook, ROOT / "src/Initial_conditions_JA_Final.xls",
                 ROOT / "config/fla_adenylate_redox_readiness.json", working_path,
                 ROOT / "output/adenylate_redox_readiness_2026_10_05_v2/coupled_sensitivity_protocol.json",
                 context / "fixed_parameters.json", context / "fixed_initial_state.csv",
                 ROOT / "src/equadiff_brodbar.py", ROOT / "src/parse_initial_conditions.py",
                 ROOT / "src/MM_calibration.py", ROOT / "src/extracellular_teacher_flux.py",
                 ROOT / "src/fla_precalibration_readiness.py"]
    hashes = {str(p.resolve()): file_hash(p) for p in preserved}
    source, ledger, times, values = workbook_evidence(workbook)
    history = history_evidence(times, source["labels"], values)
    search = search_cellbb()
    initial = np.load(ROOT / "output/fla_sparse_teacher_resolution_2026_10_05/frozen_initial_state.npz")
    readiness = evaluate_readiness(json.loads((ROOT / "config/fla_adenylate_redox_readiness.json").read_text()), root=ROOT,
        frozen_initial_redox=[float(initial["states"][list(initial["names"]).index(p)]) for p in ("NAD", "NADH")])
    protocol = json.loads(preserved[6].read_text())
    out.mkdir(parents=True)
    write_json(out / "preregistered_contract.json", {"created_at": datetime.now(timezone.utc).isoformat(), "design": design,
        "input_sha256": hashes, "optimization_performed": False, "simulations_executed": 0,
        "historical_contracts_modified": False, "time_mapping_applied": False, "normalization_applied": False})
    write_json(out / "workbook_receipt.json", source)
    write_json(out / "git_workbook_history.json", history)
    write_json(out / "cellbb_search_receipt.json", search)
    write_json(out / "public_source_review.json", design["public_sources"])
    write_json(out / "readiness_assessment.json", readiness)
    pd.DataFrame(ledger).to_csv(out / "local_row_ledger.csv", index=False)
    pd.DataFrame({"model_day_unmodified": times, "candidate_source_day_if_offset_plus_one": times-1.,
                  "mapping_verified": False, "mapping_applied": False}).to_csv(out / "time_mapping_hypothesis.csv", index=False)
    receipts = [supplementary_receipt(c, out) for c in design["supplementary_candidates"]] if fetch_supplements else []
    write_json(out / "supplementary_access_receipts.json", receipts)
    kernel_checks = {"time_unit": "day", "transport_volume_scaling": "legacy_equal_concentration",
        "measured_values_used_without_declared_volume_conversion": True,
        "inspected_paths": [str(ROOT / p) for p in ("src/MM_calibration.py", "src/parse_initial_conditions.py", "src/extracellular_teacher_flux.py")],
        "normalization_conclusion": "loaders preserve nominal numbers; upstream/model-volume compatibility is not established"}
    write_json(out / "observation_pipeline_receipt.json", kernel_checks)
    unchanged = {p: file_hash(Path(p)) == digest for p, digest in hashes.items()}
    if not all(unchanged.values()) or not history or len(readiness["blockers"]) != 13 or protocol["execution_authorized"] is not False:
        raise ValueError("preservation/readiness check failed")
    sealed_archives = {}
    for directory in ("fla_synthetic_recovery_2026_10_05_v2", "fla_teacher_resolution_2026_10_05_v2",
                      "fla_sparse_teacher_resolution_2026_10_05", "fla_smoothed_interval_replay_2026_10_05"):
        verify_archive_inputs(ROOT / "output" / directory)
        sealed_archives[directory] = True
    summary = {"status": "completed_read_only_source_units_time_audit", "rows": len(source["labels"]), "time_points": len(times),
        "elapsed_span_days": float(times[-1]-times[0]), "training_sheet_unchanged_since_first_import": all(
            r["same_concentration_values_as_current"] and r["same_time_headers_as_current"] and r["same_labels_as_current"] for r in history),
        "git_snapshots_compared": len(history), "cellbb_query_bound_to": source["metadata"]["query_bindings"],
        "cellbb_is_coefficient_import_not_verified_raw_Sheet1_source": True,
        "normalization_verified": False, "time_origin_verified": False, "measurement_lineage_verified": False,
        "scientific_blocker_count": len(readiness["blockers"]), "biological_optimization_allowed": False,
        "coupled_energy_execution_authorized": False, "simulations_executed": 0, "parameters_promoted": False,
        "sealed_prior_archives_unchanged": sealed_archives, "input_hash_checks": unchanged}
    write_json(out / "summary.json", summary)
    (out / "decision_report.md").write_text(report_text(source, history, search, receipts, readiness), encoding="utf-8")
    write_json(out / "final_verification.json", {"input_hash_checks": unchanged, "prior_archives_unchanged": sealed_archives,
        "biological_contract_changed": False, "parameters_promoted": False, "simulations_executed": 0,
        "output_sha256": {str(p.relative_to(out)): file_hash(p) for p in out.rglob("*") if p.is_file() and p.name != "final_verification.json"}})
    print(json.dumps(summary, indent=2))
    return summary


def report_text(source, history, search, receipts, readiness):
    return "\n".join([
        "# Bordbar source, units and time audit", "", "Completed 2026-10-06. Read-only analysis: no simulation, fit, source edit or model/default promotion.", "",
        "## Main findings", "",
        "1. The workbook import `cellbb` is bound to Feuil1, not Sheet1. Its named range is Feuil1!A5:F49: 44 rows of five curve coefficients (b_1 through b_5), with polynomial/log evaluation formulas. Sheet1 holds the 55 concentration rows used for training and has no formulas. Recovering cellbb.txt alone cannot establish the source of those measurement values.",
        f"2. Available workbook history snapshots compared: {len(history)}. All preserve the current concentration matrix, pool labels and time headers: {all(r['same_concentration_values_as_current'] and r['same_time_headers_as_current'] and r['same_labels_as_current'] for r in history)}. Git preservation is not publication lineage or evidence of independent measurements.",
        "3. J1-J46 is 45 elapsed days, not 46. A [primary reanalysis](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005424) explicitly describes 14 Bordbar observations over 45 days. A +1 model-origin hypothesis is plausible, but neither the original exact sampling vector nor its mapping to this workbook is verified. J38 must stay J38; it is not silently repaired. Earlier 42/46 mismatch wording does not prove extrapolation.",
        "4. A [related Bordbar uFBA study](https://www.nature.com/articles/srep46249) uses total-bag-volume mmol/L for both compartments, prioritizes assay glucose/lactate/ATP, and reports unresolved-pool processing. This is an important normalization lead, not proof of the local table's volume basis. Current loaders use nominal numbers directly and the kernel declares legacy_equal_concentration. No hematocrit, water fraction or volume scale is guessed.",
        "5. [Qi's ADSOL study](https://pmc.ncbi.nlm.nih.gov/articles/PMC5487983/) is a distinct cohort. Its relative-to-absolute/carbon normalization and variability cannot supply this workbook's missing error model.", "",
        "## Scope and data fitness", "",
        f"Workbook SHA-256: `{source['sha256']}`. All 770 concentration cells are finite and nonnegative; {source['missing_concentration_count']} missing cells. The file has no donor/replicate table, normalization equation or verified volume denominator. Exact duplicate signals remain non-independent.",
        f"Workspace search enumerated {search['files_enumerated']} files (excluding dependency/cache/Git directories); cellbb filename matches: {len(search['matching_workspace_files'])}. All-ref Git history matches: {len(search['matching_names_in_all_git_history'])}. This does not search other Desktop folders, private cloud storage or the whole machine. Enumeration errors: {len(search['enumeration_errors'])}.",
        "Primary articles were reviewed as documented in public_source_review.json. Direct PubMed/PMC/publisher requests had rate/access failures; those are not scientific evidence against a source. Supplementary downloads are accepted only after format validation; HTML delivered with HTTP 200 is not an Excel dataset. Responses and access failures are preserved separately.", "",
        "## Time and anomalous-point policy", "",
        "The reanalysis excluded source day 31 because of an extracellular anomaly. Under the unverified +1 hypothesis, this would correspond to local J32. Local EGLC rises 16.640 -> 16.950 mM from J29 to J32. That resemblance neither proves sample identity nor authorizes removing J32. No day is relabeled, dropped, imputed or extrapolated by this audit. Candidate offsets are only written to time_mapping_hypothesis.csv.", "",
        "## Evidence needed from the source owner", "",
        "Request the original concentration export feeding Sheet1 (not only cellbb.txt), metabolite dictionary and assay identity, donor/unit IDs, all original sampling times, aggregation weights/missingness handling, and the conversion script or formulas from assay quantities into each compartment's model concentration basis. Include the original raw ATP/ADP/AMP, EGLC/ELAC and BPG/PG signals. cellbb.txt remains useful for coefficient lineage only.",
        "Also request paired technical/biological replicate values and normalization factors (bag volume, hematocrit/cell-water definition if used). Independently justify biological prediction-error limits and the NAD(H) prior pool definition. Published observation counts are not evidence of the local covariance matrix or sample-mean estimator.", "",
        "## Decision", "",
        f"Scientific readiness remains blocked: {len(readiness['blockers'])} unmet checks. Keep unknown fields null and verification flags false. The prepared 19-configuration/38-replay coupled energy screen remains unauthorized. The current audit is complete; the source-content gap is not resolved by a software patch.",
        "Evidence exports: workbook_receipt.json, git_workbook_history.json, local_row_ledger.csv, observation_pipeline_receipt.json, public_source_review.json and readiness_assessment.json.", "",
        "Reproduce with `python scripts/audit_bordbar_source_units_time.py --out <fresh-directory>`; add `--fetch-supplements` for bounded public download/format checks. Historical artifacts cannot be overwritten.", ""])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fetch-supplements", action="store_true")
    args = parser.parse_args()
    run(args.config.resolve(), args.out.resolve(), fetch_supplements=args.fetch_supplements)
