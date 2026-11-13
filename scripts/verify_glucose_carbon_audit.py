"""Independent four-pool identities and source integrity; no solver calls."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(out, report):
    if report.exists():
        raise ValueError("fresh receipt required")
    summary = json.loads((out/"summary.json").read_text())
    for rel, digest in json.loads((out/"manifest.json").read_text()).items():
        assert sha(out/rel) == digest, rel
    for rel, digest in summary["input_sha256"].items():
        assert sha(ROOT/rel) == digest, rel
    prior = ROOT/"output/ak_pepase_decision_2026_11_11"
    for rel, digest in json.loads((prior/"files_seal.json").read_text()).items():
        assert sha(prior/rel) == digest, rel
    rows = list(csv.DictReader((out/"balances.csv").open()))
    fluxes = list(csv.DictReader((out/"fluxes.csv").open()))
    h = summary["hematocrit"]
    errors = []
    for row in rows:
        if row["pool"] not in ("GLC","EGLC","LAC","ELAC"):
            continue
        selected = {f["reaction"]:float(f["net_mmol_per_L_bag"]) for f in fluxes
                    if all(f[k]==row[k] for k in ("case","profile","start","end"))}
        expected = {"GLC":selected["VEGLC"]-selected["VHK"], "EGLC":-selected["VEGLC"],
                    "LAC":selected["VLDH"]-selected["VELAC"], "ELAC":selected["VELAC"]}[row["pool"]]
        errors.append(abs(float(row["delta_mmol_per_L_bag"])-expected))
    # Recompute displayed fluxes independently of the audit's integration helper.
    flux_errors = []
    paths = [ROOT/p for p in summary["input_sha256"] if p.endswith("flux_evidence.npz")]
    for path in paths:
        case = path.parents[2].name
        case = {"working_center":"control", "balanced_forward_lowered":"ak_only"}.get(case,case)
        with np.load(path) as a:
            for f in fluxes:
                if f["case"] != case or f["profile"] != path.parent.name:
                    continue
                j = a["reactions"].tolist().index(f["reaction"])
                mask = (a["q8_intervals"] >= int(f["start"])-1) & (a["q8_intervals"] < int(f["end"])-1)
                value = h*np.sum(a["q8_executed_rates"][j,mask]*a["q8_weights"][mask])
                flux_errors.append(abs(value-float(f["net_mmol_per_L_bag"])))
    assert len(errors)==200 and len(flux_errors)==400
    assert max(errors)<1e-7 and max(flux_errors)<1e-10
    receipt = dict(passed=True, four_pool_balances=len(errors), executed_fluxes=len(flux_errors),
        max_four_pool_error=max(errors), max_flux_error=max(flux_errors), new_integrations=0,
        scope="Independent transport/HK/LDH identities and flux quadrature; carbon map is explicitly declared, not independently curated",
        audit_manifest_sha256=sha(out/"manifest.json"), verifier_sha256=sha(Path(__file__)),
        runner_sha256=sha(ROOT/"scripts/audit_glucose_carbon.py"))
    report.mkdir(parents=True)
    (report/"verification.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    (report/"manifest.json").write_text(json.dumps({"verification.json":sha(report/"verification.json")},indent=2))
    print(json.dumps(receipt,indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a = p.parse_args()
    verify(a.out.resolve(),a.report.resolve())
