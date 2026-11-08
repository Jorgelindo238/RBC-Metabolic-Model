"""Separate stoichiometric ARGSL follow-up after the forward-arginase screen."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_balance_feasibility import integral_balance_screen
from fla_balance_certificates import balance_certificates
from fla_joint_calibration import JointRHS
from rbc_gem_audit import pool_mapping, project_gem
from run_protected_joint import verify_inputs, check_seal
from run_glut_only_free_replay import write, sha

CONFIG = ROOT/"config/fla_asl_coverage_followup.json"


def run(out):
    if out.exists(): raise ValueError("fresh separate follow-up required")
    d = json.loads(CONFIG.read_text()); parent = ROOT/d["parent_archive"]
    f = verify_inputs(parent); check_seal(parent/"coverage")
    model_path = ROOT/f["design"]["gem_archive"]/"github/1.3.0/model/RBC-GEM.json"
    model = json.loads(model_path.read_text())
    source = next(r for r in model["reactions"] if r["id"] == d["source_GEM_reaction"])
    projected, missing, currency = project_gem(source, {v:k for k, v in pool_mapping(model).items()})
    if missing or source["lower_bound"] >= 0 or source["upper_bound"] <= 0: raise ValueError("signed closed ARGSL source contract failed")
    rhs = JointRHS(f["parameters"], f["kinetics"])
    cov = json.loads((parent/"coverage/summary.json").read_text())
    rows = []
    out.mkdir(parents=True)
    for end in d["horizons"]:
        old = next(r for r in cov["balance_relaxations"] if r["label"] == "both_candidates" and r["end_day"] == end)
        with np.load(parent/"coverage"/f"both_candidates_J{end}.npz") as a:
            column = np.array([projected.get(p, 0.) for p in old["pools"]])
            matrix = np.column_stack([a["matrix"], column])
            reactions = list(old["reaction_names"])+["VASL_structural_only"]
            bounds = [(0., None) if r in old["forward_reactions"] else (None, None) for r in reactions]
            result = integral_balance_screen(matrix, a["observed"], a["time"], a["errors"], reaction_bounds=bounds)
            cert = balance_certificates(matrix, a["observed"], a["time"], a["errors"], old["pools"],
                [reactions.index(r) for r in old["forward_reactions"]])
            lower = max(c["minimum_working_multiplier_lower_bound"] for c in cert)
            result.update(end_day=end, previous_multiplier=old["minimum_working_error_multiplier"],
                rank=int(np.linalg.matrix_rank(matrix)), previous_rank=old["measured_row_rank"],
                certificates=cert, numerical_primal_lower_bound_gap=result["minimum_working_error_multiplier"]-lower,
                reaction_names=reactions, pools=old["pools"], new_active_ODE_branches=[],
                finite_latent_ARGSUCC_stock_constraint_imposed=False)
            np.savez_compressed(out/f"J{end}.npz", matrix=matrix, observed=a["observed"], time=a["time"], errors=a["errors"],
                extents=np.array(result["executed_extent_integrals"]), adjustments=np.array(result["hypothetical_observation_adjustments_mM"]))
        rows.append(result)
    write(out/"summary.json", {"design": d, "source_reaction": source, "projected_stoichiometry": projected,
        "omitted_currency": currency, "source_ASL_evidence": cov["CITR_gene_and_protein_evidence"]["ASL"],
        "source_ASS1_evidence_for_future_curation": cov["CITR_gene_and_protein_evidence"]["ASS1"],
        "results": rows, "CITR_dynamic_coverage_resolved": False, "used_for_parameter_selection": False,
        "interpretation": "optimistic_extent_cone_not_kinetic_fit_or_full_latent_inventory_feasibility"})
    paths = [CONFIG, Path(__file__), model_path, parent/"execution_design.json", parent/"coverage/summary.json",
        ROOT/"src/fla_balance_feasibility.py", ROOT/"src/fla_balance_certificates.py"]
    write(out/"manifest.json", {"input_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in paths},
        "output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return [{"end_day": r["end_day"], "previous_multiplier": r["previous_multiplier"],
        "multiplier": r["minimum_working_error_multiplier"], "rank": r["rank"],
        "bound_gap": r["numerical_primal_lower_bound_gap"]} for r in rows]


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    with threadpool_limits(1): result = run(a.out.resolve())
    print(json.dumps(result, indent=2))
