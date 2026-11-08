"""Independently check the read-only source audit against workbook cells and loaders."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
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
from extracellular_teacher_flux import load_bordbar_extracellular_data
from fla_precalibration_readiness import evaluate_readiness
from run_fla_sparse_teacher_resolution import verify_archive_inputs


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify(out):
    checks = []

    def check(name, result):
        checks.append({"name": name, "passes": bool(result)})

    contract = read(out / "preregistered_contract.json")
    final = read(out / "final_verification.json")
    summary = read(out / "summary.json")
    for filename, value in contract["input_sha256"].items():
        check(f"input:{filename}", digest(Path(filename)) == value)
    for filename, value in final["output_sha256"].items():
        check(f"output:{filename}", digest(out / filename) == value)
    check("read_only_scope", contract["simulations_executed"] == summary["simulations_executed"] == 0
          and not contract["optimization_performed"] and not contract["historical_contracts_modified"]
          and not contract["time_mapping_applied"] and not contract["normalization_applied"]
          and not final["biological_contract_changed"] and not summary["parameters_promoted"])
    source = read(out / "workbook_receipt.json")
    workbook_path = ROOT / contract["design"]["workbook"]
    workbook = load_workbook(workbook_path, read_only=True, data_only=False)
    sheet = workbook["Sheet1"]
    times = np.asarray([c.value for c in next(sheet.iter_rows(min_row=1, max_row=1))[1:]], dtype=float)
    rows = list(sheet.iter_rows(min_row=2))
    labels = [str(row[0].value).strip().upper() for row in rows]
    values = np.asarray([[c.value for c in row[1:]] for row in rows], dtype=float)
    check("workbook_digest", digest(workbook_path) == source["sha256"])
    check("matrix_and_elapsed_time", values.shape == tuple(source["shape"]) == (55, 14)
          and np.isfinite(values).all() and (values >= 0).all()
          and times.tolist() == source["model_days"] and times[-1]-times[0] == source["elapsed_span_days"] == 45.)
    check("no_training_formulas", all(c.data_type != "f" for row in rows for c in row))
    ledger = pd.read_csv(out / "local_row_ledger.csv", float_precision="round_trip")
    check("ledger_labels", ledger.pool.tolist() == labels == source["labels"])
    for i, row in enumerate(rows):
        saved = ledger.iloc[i]
        check(f"source_cells:{labels[i]}", saved.label_cell == row[0].coordinate
              and saved.first_cell == row[1].coordinate and saved.last_cell == row[-1].coordinate
              and np.array_equal([saved.J1_nominal_mM, saved.J4_nominal_mM, saved.J46_nominal_mM], values[i, [0, 1, -1]])
              and not saved.upstream_row_mapping_verified and not saved.volume_basis_verified
              and not saved.aggregation_and_replicates_verified)
    with zipfile.ZipFile(workbook_path) as archive:
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        metadata = ET.fromstring(archive.read("xl/workbook.xml"))
        named = metadata.find("m:definedNames/m:definedName[@name='cellbb']", ns)
        check("cellbb_named_range", named is not None and named.text == "Feuil1!$A$5:$F$49"
              and named.get("localSheetId") == "1")
        relationships = ET.fromstring(archive.read("xl/worksheets/_rels/sheet2.xml.rels"))
        check("cellbb_query_sheet2", any(r.get("Type", "").endswith("/queryTable")
              and r.get("Target") == "../queryTables/queryTable1.xml" for r in relationships))
        relationships = ET.fromstring(archive.read("xl/worksheets/_rels/sheet1.xml.rels"))
        check("no_query_on_Sheet1", not any(r.get("Type", "").endswith("/queryTable") for r in relationships))
    coefficient_sheet = workbook["Feuil1"]
    saved_table = source["metadata"]["cellbb_coefficient_table"]
    check("five_coefficient_columns", [coefficient_sheet.cell(5, i).value for i in range(2, 7)]
          == ["b_1", "b_2", "b_3", "b_4", "b_5"] and len(saved_table["rows"]) == 44)
    for saved in saved_table["rows"]:
        check(f"coefficient_row:{saved['row']}", np.array_equal(saved["coefficients"],
              [coefficient_sheet.cell(saved["row"], i).value for i in range(2, 7)]))
    workbook.close()
    offset = pd.read_csv(out / "time_mapping_hypothesis.csv")
    check("offset_not_applied", np.array_equal(offset.model_day_unmodified, times)
          and np.array_equal(offset.candidate_source_day_if_offset_plus_one, times-1.)
          and not offset.mapping_verified.any() and not offset.mapping_applied.any())
    for saved in read(out / "git_workbook_history.json"):
        blob = subprocess.check_output(["git", "show", f"{saved['commit']}:{saved['path']}"], cwd=ROOT)
        frame = pd.read_excel(BytesIO(blob), sheet_name="Sheet1")
        same_values = np.array_equal(frame.iloc[:, 1:].to_numpy(dtype=float), values)
        same_times = np.array_equal(np.asarray(frame.columns[1:], dtype=float), times)
        same_labels = frame.iloc[:, 0].astype(str).str.strip().str.upper().tolist() == labels
        check(f"git_snapshot:{saved['commit']}:{saved['path']}", hashlib.sha256(blob).hexdigest() == saved["blob_sha256"]
              and same_values == saved["same_concentration_values_as_current"]
              and same_times == saved["same_time_headers_as_current"] and same_labels == saved["same_labels_as_current"])
    external_times, external = load_bordbar_extracellular_data(workbook_path)
    check("teacher_loader_time_parity", np.array_equal(times, external_times) and len(external) == 19)
    for pool, vector in external.items():
        check(f"teacher_loader_values:{pool}", np.array_equal(values[labels.index(pool)], vector))
    # Extract only the data-loading function; avoid importing calibration runtime side effects.
    module = ast.parse((ROOT / "src/MM_calibration.py").read_text(encoding="utf-8-sig"))
    function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "load_experimental_data")
    namespace = {"pd": pd, "np": np, "DATA_DIR": ROOT / "src"}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "isolated_loader", "exec"), namespace)
    loaded_times, loaded_values, mapping = namespace[function.name]()
    check("calibration_loader_time_parity", np.array_equal(times, loaded_times))
    for i, pool in enumerate(labels):
        check(f"calibration_loader_values:{pool}", np.array_equal(values[i], loaded_values[mapping[pool]]))
    module = ast.parse((ROOT / "src/equadiff_brodbar.py").read_text(encoding="utf-8-sig"))
    constants = {}
    for node in module.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            constants.update({n.id: node.value.value for n in node.targets if isinstance(n, ast.Name)})
    pipeline = read(out / "observation_pipeline_receipt.json")
    check("kernel_metadata", constants["MODEL_TIME_UNIT"] == pipeline["time_unit"] == "day"
          and constants["TRANSPORT_VOLUME_SCALING_MODE"] == pipeline["transport_volume_scaling"] == "legacy_equal_concentration")
    initial = np.load(ROOT / "output/fla_sparse_teacher_resolution_2026_10_05/frozen_initial_state.npz")
    readiness = evaluate_readiness(read(ROOT / "config/fla_adenylate_redox_readiness.json"), root=ROOT,
        frozen_initial_redox=[float(initial["states"][list(initial["names"]).index(pool)]) for pool in ("NAD", "NADH")])
    check("readiness_not_bypassed", len(readiness["blockers"]) == summary["scientific_blocker_count"] == 13
          and not summary["biological_optimization_allowed"] and not summary["coupled_energy_execution_authorized"])
    for archive in summary["sealed_prior_archives_unchanged"]:
        verify_archive_inputs(ROOT / "output" / archive)
        check(f"sealed_archive:{archive}", True)
    for receipt in read(out / "supplementary_access_receipts.json"):
        if "local_response_file" in receipt:
            check(f"public_response:{receipt['expected_format']}", digest(out / receipt["local_response_file"]) == receipt["response_sha256"]
                  and (receipt["usable_spreadsheet"] or receipt["local_response_file"].endswith(".bin")))
    suites = list(ET.parse(out / "qa_results.xml").getroot().iter("testsuite"))
    qa = {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    check("QA", qa["tests"] > 0 and qa["failures"] == qa["errors"] == qa["skipped"] == 0)
    report = {"independent_checks_pass": all(c["passes"] for c in checks), "check_count": len(checks),
              "checks": checks, "qa": qa, "scope": "all 770 calibration cells, 266 extracellular cells, workbook XML, Git snapshots and sealed archives"}
    (out / "independent_verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["independent_checks_pass"]:
        raise ValueError([c["name"] for c in checks if not c["passes"]])
    final.update(independently_verified_at=datetime.now(timezone.utc).isoformat(), independent_archive_checks_pass=True,
        independent_archive_check_count=len(checks), qa=qa,
        supporting_code_sha256={str(p): digest(p) for p in (Path(__file__), ROOT / "qa/test_bordbar_source_units_time_audit.py")},
        output_sha256={str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()
                      and p.name != "final_verification.json"})
    (out / "final_verification.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "output/bordbar_source_units_time_audit_2026_10_06")
    result = verify(parser.parse_args().out.resolve())
    print({key: value for key, value in result.items() if key != "checks"})
