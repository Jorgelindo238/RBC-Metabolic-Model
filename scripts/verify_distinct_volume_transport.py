"""Reopen source cells, verify archived numerical budgets and protect history."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rbc_distinct_volume_transport import equadiff_distinct_volume, phase_matrix
from reaction_positivity import rbc_reaction_matrix


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def verify(out):
    checks = 0
    def require(value, message):
        nonlocal checks
        checks += 1
        if not value:
            raise ValueError(message)
    context = out / "fixed_context_v2"
    contract = json.loads((context / "preregistered_contract.json").read_text())
    design = contract["design"]
    summary = json.loads((context / "summary.json").read_text())
    for p, expected in contract["input_sha256"].items():
        require(sha(ROOT / p) == expected, "protected input changed " + p)
    if (out / "manifest.json").exists():
        seal = json.loads((out / "manifest.json").read_text())
        for p, expected in seal["output_sha256"].items():
            require(sha(out / p) == expected, "sealed output changed " + p)
        for p, expected in seal["input_sha256"].items():
            require(sha(ROOT / p) == expected, "sealed source changed " + p)
    data = out / "source_preparation"
    samples = read_csv(data / "sample_keys.csv")
    require(len(samples) == 372 and len({r["working_sample_key"] for r in samples}) == 372, "sample key coverage")
    require(len({r["trajectory_key"] for r in samples}) == 36, "trajectory key coverage")
    require(all(not r["donor_id"] and r["cross_sheet_pairing_verified"] == "False" for r in samples), "invented donor identity")
    require(len({r["validation_split_key"] for r in samples}) == 1, "unknown donors must remain one conservative split group")
    wb = openpyxl.load_workbook(ROOT / design["jbc_workbook"], read_only=True, data_only=True)
    tables = {s.title: list(s.values) for s in wb}
    wb.close()
    def cell(locator):
        sheet, coord = locator.split("!")
        row, col = openpyxl.utils.cell.coordinate_to_tuple(coord)
        return tables[sheet][row - 1][col - 1]
    records = read_csv(data / "phase_observations_pairing_sensitivity.csv")
    require(len(records) == 144, "pairing records missing")
    require(len({r["pairing_id"] for r in records}) == 6, "six pairing alternatives required")
    unique = {(r["pairing_id"], r["endo_trajectory_key"], r["source_day"]) for r in records}
    require(len(unique) == 144, "duplicate paired record")
    for r in records:
        h = float(r["hematocrit"])
        require(h == cell("assay!" + r["hematocrit_source_cell"]), "hematocrit source mismatch")
        require(not r["donor_id"] and r["pairing_verified"] == "False" and r["training_enabled"] == "False", "unverified pairing enabled")
        for pool in ("GLC", "LAC", "EGLC", "ELAC"):
            value = float(r[pool + "_phase_mM"])
            require(value == cell(r[pool + "_source_cell"]), "source concentration rescaled")
            volume = h if pool in ("GLC", "LAC") else 1 - h
            require(float(r[pool + "_amount_per_L_bag"]) == volume * value, "amount ledger mismatch")
    bounds = read_csv(out / "conditional_mct_directionality_bounds.csv")
    require(len(bounds) == 144, "MCT directionality coverage")
    paired = {(r["pairing_id"], r["endo_trajectory_key"], r["assay_trajectory_key"], float(r["source_day"])): r for r in records}
    for b in bounds:
        r = paired[b["pairing_id"], b["endo_key"], b["assay_key"], float(b["source_day"])]
        require(float(b["delta_pH_export_upper_bound"]) == math.log10(float(r["LAC_phase_mM"]) / float(r["ELAC_phase_mM"])), "MCT conditional bound mismatch")
        require(b["measured_pH"] == "False" and b["free_activity_mapping_verified"] == "False", "conditional bound falsely treated as measured pH")
    params = json.loads((ROOT / design["initial_state_archive"] / "frozen_parameters.json").read_text())
    initial = np.array(contract["initial_state"])
    names, reactions, common_s = rbc_reaction_matrix(params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    limits = json.loads((ROOT / design["working_reference"]).read_text())["validation_before_calibration"]
    def close(a, b, kind):
        return np.all(np.abs(a - b) <= limits[kind + "_atol_mM"] + limits[kind + "_rtol"] * np.maximum(abs(a), abs(b)))
    require(len(summary["results"]) == 14, "fixed replay coverage")
    for case in contract["cases"]:
        pair = []
        for tol in design["tolerances"]:
            archive = np.load(context / (case["name"] + "_" + tol) / "replay.npz")
            x, t = archive["states"], archive["time"]
            require(np.array_equal(archive["initial"], initial) and np.array_equal(archive["accepted_states"][:, 0], initial), "initial state changed")
            require(archive["accepted_time"][0] == 1 and archive["accepted_time"][-1] == 4, "truncated replay")
            require(np.all(np.isfinite(x)) and min(x[:113].min(), archive["accepted_states"][:113].min()) >= -1e-10, "invalid/negative state")
            require(np.all(x[-1] == initial[-1]), "clamped pHi changed")
            matrix = common_s if case["h"] is None else phase_matrix(case["h"])[2]
            require(np.array_equal(matrix, archive["matrix"]), "phase matrix mismatch")
            indices = [np.where(t == b)[0][0] for b in archive["boundaries"]]
            require(close(np.diff(x[:113, indices], axis=1), matrix @ archive["executed8"], "quadrature"), "executed integrated budget mismatch")
            require(close(archive["raw4"], archive["raw8"], "quadrature"), "native quadrature mismatch")
            require(close(archive["executed4"], archive["executed8"], "quadrature"), "executed quadrature mismatch")
            kwargs = {"mode": case["mode"], "custom_params": params, "positivity_policy": "reaction_consistent",
                      "reaction_availability_threshold": .001, "ph_policy": "clamped_diagnostic"}
            if case["h"] is not None:
                kwargs["hematocrit"] = case["h"]
            if case["mode"] == "phase_glut_mct":
                kwargs.update(transport_kinetics=contract["kinetics"], phe=design["reversible_kinetics"]["pHe_diagnostic"])
            for idx in (0, 50, 100, 150, 200, 250, 300):
                audit = {}
                d = equadiff_distinct_volume(t[idx], x[:, idx], numerical_audit=audit, **kwargs)
                v = np.array([audit["effective_fluxes"][r] for r in reactions])
                require(np.allclose(matrix @ v, d[:113], rtol=1e-12, atol=1e-12), "live RHS closure")
                if case["mode"] == "phase_glut_mct":
                    require(audit["MCT_proton_export_per_L_bag_day"] == case["h"] * v[reactions.index("VELAC")], "proton ledger mismatch")
            pair.append((x[:113], archive["executed8"]))
        require(close(pair[0][0], pair[1][0], "comparison"), "strict/ultrastrict state divergence")
        require(close(pair[0][1], pair[1][1], "comparison"), "strict/ultrastrict flux divergence")
    require(summary["numerical_pass"] is True and summary["biological_promotion"] is False, "incorrect promotion/summary")
    return {"verified": True, "checks": checks, "source_pairing_records": 144,
            "fixed_replays": 14, "donor_identity_verified": False, "biological_promotion": False}


def seal(out):
    if (out / "manifest.json").exists():
        raise ValueError("do not rewrite an existing seal")
    evidence = verify(out)
    protected = json.loads((out / "fixed_context_v2/preregistered_contract.json").read_text())["input_sha256"]
    files = [Path(__file__), ROOT / "scripts/prepare_yurkovich_phase_keys.py",
             ROOT / "scripts/report_distinct_volume_transport.py",
             ROOT / "qa/test_distinct_volume_transport.py", ROOT / "tasks/fla_distinct_volume_transport_2026_10_06.md"]
    protected.update({str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in files})
    outputs = {str(p.relative_to(out)).replace("\\", "/"): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}
    (out / "manifest.json").write_text(json.dumps({"input_sha256": protected,
        "output_sha256": outputs, "verification_before_seal": evidence}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    if args.seal:
        seal(args.out.resolve())
    print(json.dumps(verify(args.out.resolve()), indent=2))
