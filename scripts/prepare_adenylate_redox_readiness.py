"""Verify scientific prerequisites and prepare, but do not run, energy probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_coupled_energy_protocol import build_sensitivity_plan, resolved_parameters
from fla_precalibration_readiness import endpoint_checks, evaluate_readiness, propagate_adenylate_uncertainty, require_scientific_contract

DEFAULT_CONFIG = ROOT / "config/fla_adenylate_redox_readiness.json"
DEFAULT_SOURCE = ROOT / "output/adenylate_redox_feasibility_2026_10_05"
DEFAULT_OUT = ROOT / "output/adenylate_redox_readiness_2026_10_05_v2"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def source_receipt(workbook_path, historical_path):
    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    sheet = workbook["Sheet1"]
    rows = {}
    for row in sheet.iter_rows():
        label = str(row[0].value).strip().upper()
        if label in ("ATP", "ADP", "AMP"):
            if label in rows:
                raise ValueError("duplicate adenylate observation label")
            rows[label] = {"sheet": sheet.title, "label_cell": row[0].coordinate,
                           "J1_cell": row[1].coordinate, "J4_cell": row[2].coordinate,
                           "J1_nominal_mM": float(row[1].value), "J4_nominal_mM": float(row[2].value)}
    unit_label, days = sheet["A1"].value, [float(sheet["B1"].value), float(sheet["C1"].value)]
    workbook.close()
    if set(rows) != {"ATP", "ADP", "AMP"} or days != [1., 4.]:
        raise ValueError("expected three nominal J1/J4 adenylate rows")
    history = pd.read_excel(historical_path, header=None)
    historical = {}
    for pool in ("NAD", "NADH", "NADP", "NADPH"):
        selected = history.index[history.iloc[:, 0].astype(str).str.strip().str.upper().eq(pool)]
        if len(selected) != 1:
            raise ValueError("unique historical redox row required")
        row = int(selected[0])
        historical[pool] = {"row_1_based": row + 1, "nominal_mM": float(history.iloc[row, 1])}
    connections = []
    with zipfile.ZipFile(workbook_path) as archive:
        if "xl/connections.xml" in archive.namelist():
            document = ET.fromstring(archive.read("xl/connections.xml"))
            for node in document:
                connections.append({"attributes": dict(node.attrib),
                    "child_attributes": [{"tag": child.tag.rsplit("}", 1)[-1], "attributes": dict(child.attrib)} for child in node]})
    return {"scope": "local nominal values and workbook metadata only; not raw measurement lineage",
            "workbook_sha256": digest(workbook_path), "historical_sha256": digest(historical_path),
            "nominal_unit_label": unit_label, "nominal_model_days": days, "adenylate_cells": rows,
            "historical_redox_cells": historical, "workbook_connections_unverified_leads": connections,
            "external_connection_followed": False, "biological_normalization_verified": False,
            "public_primary_sources": [
                {"url": "https://pubmed.ncbi.nlm.nih.gov/26749434/", "doi": "10.1111/trf.13460",
                 "scope": "publication candidate: 20 SAGM units over 42 days; not a verified mapping to the 46-day local workbook"},
                {"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5487983/", "doi": "10.3390/metabo7020012",
                 "scope": "Qi uses a separate ADSOL cohort and a relative-to-absolute normalization method; its variability cannot be assigned to this workbook"}],
            "literature_uncertainty_imported": False, "prior_bounds_inferred_from_historical_point": False}


def run(config_path=DEFAULT_CONFIG, source=DEFAULT_SOURCE, out_dir=DEFAULT_OUT):
    if out_dir.exists():
        raise FileExistsError("use a fresh output directory; archived evidence is not overwritten")
    prior = json.loads((source / "preregistered_contract.json").read_text())
    prior_summary = json.loads((source / "summary.json").read_text())
    if prior_summary.get("numerical_diagnostic_passes") is not True:
        raise ValueError("verified numerical source diagnostic required")
    for path, expected in prior["input_sha256"].items():
        if digest(path) != expected:
            raise ValueError(f"archived diagnostic input changed: {path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    initial = prior["scenario_initial_states"]["baseline"]
    assessment = evaluate_readiness(config, root=ROOT, frozen_initial_redox=[initial["NAD"], initial["NADH"]])
    fixed_context = ROOT / prior["working_reference"]["fixed_context"]
    params_path = fixed_context / "fixed_parameters.json"
    parameters = json.loads(params_path.read_text())
    resolved, provenance = resolved_parameters(parameters, ROOT / "src/equadiff_brodbar.py")
    plan = build_sensitivity_plan(resolved)
    plan.update(resolved_capacities=resolved, resolved_capacity_provenance=provenance,
                working_reference=prior["working_reference"],
                scientific_contract_complete=assessment["scientific_contract_complete"],
                execution_authorized=False, simulations_executed=0,
                endpoint_limits=config["accuracy"]["absolute_endpoint_error_mM"])
    workbook = ROOT / "src/Data_Bordbar_et_al_exp.xlsx"
    historical = ROOT / "src/Initial_conditions_JA_Final.xls"
    receipt = source_receipt(workbook, historical)
    reference = pd.read_csv(source / "reference_endpoints.csv")
    if list(reference.day) != [1., 4.] or any(not np.allclose(reference[pool],
            [receipt["adenylate_cells"][pool]["J1_nominal_mM"], receipt["adenylate_cells"][pool]["J4_nominal_mM"]],
            rtol=0, atol=1e-12) for pool in ("ATP", "ADP", "AMP")):
        raise ValueError("archived reference endpoints differ from the actual workbook cells")
    predicted = pd.read_csv(source / "J4_endpoint_diagnostics.csv")
    rows = []
    for (case, solver), selected in predicted.groupby(["case", "solver"]):
        selected = selected.set_index("pool")
        expected = np.asarray([reference[pool].iloc[1] for pool in ("ATP", "ADP", "AMP")])
        for row in endpoint_checks(expected, np.asarray([selected.loc[pool, "model_J4_mM"] for pool in ("ATP", "ADP", "AMP")]), config,
                                   root=ROOT, frozen_initial_redox=[initial["NAD"], initial["NADH"]]):
            rows.append({"case": case, "solver": solver, **row})
    out_dir.mkdir(parents=True)
    inputs = [config_path, source / "preregistered_contract.json", source / "summary.json", source / "reference_endpoints.csv",
              source / "J4_endpoint_diagnostics.csv", params_path, workbook, historical, Path(__file__),
              ROOT / "src/fla_precalibration_readiness.py", ROOT / "src/fla_coupled_energy_protocol.py"]
    input_hashes = {**prior["input_sha256"], **{str(path.resolve()): digest(path) for path in inputs}}
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(), "input_sha256": input_hashes,
                "scientific_contract": config, "assessment": assessment,
                "simulations_executed": 0, "optimization_performed": False,
                "historical_audit_sources_modified": False}
    save_json(out_dir / "readiness_contract.json", manifest)
    save_json(out_dir / "source_receipt.json", receipt)
    save_json(out_dir / "coupled_sensitivity_protocol.json", plan)
    save_json(out_dir / "joint_endpoint_checks.json", rows)
    if config["uncertainty"]["verified"] is True and assessment["scientific_contract_complete"]:
        means = [float(reference[pool].iloc[day]) for day in (0, 1) for pool in ("ATP", "ADP", "AMP")]
        save_json(out_dir / "propagated_uncertainty.json", propagate_adenylate_uncertainty(means, config["uncertainty"]["covariance_mM2"]))
    report = ["# Scientific readiness and prepared coupled energy protocol", "",
        "This pass prepares and verifies evidence requirements. It performs no simulation, optimization, kinetic change, redox IC change or model promotion. The preceding eight fixed-kinetic J1-J4 replays remain the only simulation evidence.", "",
        "## Decision", "", f"Scientific contract complete: {assessment['scientific_contract_complete']}. Optimization allowed: False. Coupled probe execution authorized: False.", "",
        "## Evidence checks", "", "| Check | Pass | Requirement |", "|---|---|---|"]
    report.extend(f"| {check['name']} | {check['passed']} | {check['requirement']} |" for check in assessment["checks"])
    report += ["", "## What is verified and what remains unknown", "",
        "Local ATP/ADP/AMP cells, nominal mM labels, J1/J4 headers, historical redox values and unchanged source hashes are verified. This establishes local reproducibility, not the upstream measurement normalization or uncertainty. Workbook external-connection metadata is recorded only as a lead; no external file is read or assumed to contain these measurements.", "",
        "The [Bordbar publication candidate](https://pubmed.ncbi.nlm.nih.gov/26749434/) describes 20 SAGM units and 42-day storage. [Qi et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5487983/) use a separate ADSOL cohort and their own normalization. Neither proves the local 46-day workbook mapping, and Qi's process variability is not imported as this dataset's error. Historical redox points do not define a supported prior interval.", "",
        "## Required evidence before fitting", "",
        "1. Exact source table/worksheet mapping for ATP, ADP, AMP, and corresponding unit/donor IDs.",
        "2. Source concentration basis, normalization formula, intracellular volume/water or cell-count basis, and traceable factors into model mM. An mM header alone is insufficient.",
        "3. Biological sampling origin and exact source-to-model day mapping, especially the 42/46-day mismatch.",
        "4. Paired biological/technical measurements or validated assay covariance, including all cross-pool/cross-day terms. Specify whether the target is an individual unit, a population distribution or a mean; SD and SEM are not interchangeable.",
        "5. Three separately justified absolute J4 endpoint tolerances in mM, frozen before fitting. A predeclared prediction requirement is valid if explicitly justified; no threshold is inferred from the failed simulations or solver error. Full-panel nRMSE guards are a separate, still-unresolved requirement.",
        "6. Applicable redox total/fraction prior bounds with the same compartment, concentration basis and storage context. The current fixed initialization must be inside them or a separate, reversible IC decision is required.", "",
        "Redox prior values must also describe the modeled pool: free reaction-available NAD(H) and total extractable NAD(H) cannot be interchanged without a separate supported binding/availability model. [Simpson et al., 1982](https://www.cruk.cam.ac.uk/publications/studies-of-lactate-dehydrogenase-in-the-purified-state-and-in-intact-erythrocytes/) experimentally distinguish those pools; their point estimates are not adopted as stored-RBC prior bounds here.", "",
        "## Joint uncertainty, without guessed independence", "",
        "Observation order: (ATP_J1, ADP_J1, AMP_J1, ATP_J4, ADP_J4, AMP_J4). Supply the full positive-semidefinite covariance C in mM^2. For total-pool change, Var(delta T)=a^T C a, a=(-1,-1,-1,1,1,1). Per-pool changes use D=(-I,I). At each endpoint, energy-charge uncertainty uses the first-order gradient of (ATP+0.5 ADP)/T. Missing covariance is not replaced by a diagonal or zero matrix; no biological accuracy limit is inferred automatically.", "",
        "## Prepared dynamic sensitivity, not calibration", "",
        "Three coherent capacity groups: HK/PFK investment (downward-only, retaining HK<=5.0), AK forward/reverse together, and GAPDH/PGK together. Single-group log steps 0.05 and 0.10 give 11 configurations including baseline. Eight paired-group configurations at 0.05 give 19 total configurations and 38 planned strict/ultrastrict replays. Probe sizes are diagnostic finite-difference steps, not verified biological bounds.", "",
        "Investment derivatives are one-sided because HK is at its ceiling; other group derivatives are central. The pairs expose dynamic interactions while retaining full ATP/ADP/AMP, purine, redox, executed-flux and limiter budgets. Keep every unlisted parameter, measured and latent IC, network and numerical threshold fixed. No best case, objective scalarization, observation resets or artificial ATP source. The plan remains prepared, not executed, until scientific readiness and a separate execution decision are established.", "",
        "## Reproduction", "",
        "`python scripts/prepare_adenylate_redox_readiness.py --out-dir <fresh-directory>` builds evidence and the plan only. Add `--require-ready` to return exit code 2 if prerequisites are unresolved. This scoped guard is not wired into historical calibration runners or the full platform, and cannot authorize fitting by itself."]
    (out_dir / "decision_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out_dir / "decision_report.md"), "status": assessment["status"], "planned_replays": 38, "simulations_executed": 0, "optimization_allowed": False}))
    return assessment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)
    assessment = run(args.config, args.source, args.out_dir)
    if args.require_ready:
        try:
            config = json.loads(args.config.read_text(encoding="utf-8"))
            source_contract = json.loads((args.source / "preregistered_contract.json").read_text())
            initial = source_contract["scenario_initial_states"]["baseline"]
            require_scientific_contract(config, root=ROOT, frozen_initial_redox=[initial["NAD"], initial["NADH"]])
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
