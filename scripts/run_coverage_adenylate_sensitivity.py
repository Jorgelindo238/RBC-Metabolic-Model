"""Pinned-source coverage resolution, then two-step adenylate sensitivities."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_adenylate_sensitivity import resolve_parameters, perturb, diagnostics, sensitivity_column, select_subset, admissibility, ADENYLATES, PROTECTED
from fla_broad_protected_calibration import POOLS, predict_broad, training_data
from fla_joint_calibration import JointRHS
from fla_balance_feasibility import integral_balance_screen
from fla_balance_certificates import balance_certificates
from fla_network_observation_coverage import channel_coverage, volume_conservation_diagnostic
from rbc_coverage_extensions import BRANCHES, extend_matrix
from rbc_gem_audit import pool_mapping, project_gem
from rbc_stoichiometry import REACTION_PARAMS
from run_protected_joint import verify_inputs, seal, check_seal
from run_glut_only_free_replay import write, sha
from run_broad_protected_joint import audit

CONFIG = ROOT/"config/fla_coverage_adenylate_sensitivity.json"


def prepare(out):
    from verify_fla_objective_reformulation import verify
    if out.exists(): raise ValueError("fresh coverage/sensitivity archive required")
    d = json.loads(CONFIG.read_text())
    parent = ROOT/d["parent_archive"]
    with threadpool_limits(1): receipt = verify(parent)
    prior = json.loads((parent/"execution_design.json").read_text())
    baseline = json.loads((parent/"fits"/d["baseline_label"]/"result.json").read_text())
    obs = json.loads((parent/"observations.json").read_text())
    f = {key: prior[key] for key in ("parent_design", "initial", "guards", "kinetics")}
    f.update(design=d, parameters=baseline["parameters"], scales=prior["phases"]["15"]["scales"], parent_verification=receipt)
    f["resolved_parameters"] = resolve_parameters(f["parameters"], ROOT/"src/equadiff_brodbar.py", d["parameters"])
    f["parameter_scopes"] = {p: sorted(r for r, names in REACTION_PARAMS.items() if p in names) for p in d["parameters"]}
    gem = ROOT/d["gem_archive"]
    required = [gem/"github/1.3.0/model/RBC-GEM.json", gem/"github/1.3.0/data/curation/genes_evidence.tsv",
        gem/"github/1.3.0/data/curation/reactions_evidence.tsv", gem/"retrieval_receipts.json",
        ROOT/"output/palsson_proteomics_review_2026_10_06/human_protein_copy_numbers.csv"]
    receipts = json.loads((gem/"retrieval_receipts.json").read_text())
    for path in required[:3]:
        record = next(r for r in receipts if r["file"] == path.relative_to(gem).as_posix())
        if sha(path) != record["sha256"] or d["gem_commit"] not in record["url"]: raise ValueError("pinned GEM evidence changed")
    paths = [CONFIG, Path(__file__), ROOT/"src/rbc_coverage_extensions.py", ROOT/"src/fla_network_observation_coverage.py",
        ROOT/"src/fla_adenylate_sensitivity.py", ROOT/"qa/test_coverage_adenylate_sensitivity.py",
        ROOT/"scripts/verify_coverage_adenylate_sensitivity.py", parent/"execution_design.json", parent/"observations.json",
        parent/"summary.json", parent/"manifest.json", parent/"fits"/d["baseline_label"]/"result.json"]
    paths += required+[ROOT/p for p in prior["input_sha256"]]
    f["input_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    out.mkdir(parents=True); write(out/"execution_design.json", f); write(out/"observations.json", obs)
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return {"prepared": True, "parent_checks": receipt["checks"], "parameters": len(d["parameters"]),
        "registered_fast_ODE_probes": 1+4*len(d["parameters"]), "optimization": False, "branches_active_in_sensitivity": []}


def coverage(out, f):
    folder = out/"coverage"
    if (folder/"files_seal.json").exists():
        check_seal(folder); return json.loads((folder/"summary.json").read_text())
    if folder.exists(): raise ValueError("partial coverage audit requires successor")
    folder.mkdir()
    d = f["design"]; gem = ROOT/d["gem_archive"]
    model = json.loads((gem/"github/1.3.0/model/RBC-GEM.json").read_text())
    source = {r["id"]:r for r in model["reactions"]}; inverse = {v:k for k, v in pool_mapping(model).items()}
    with (gem/"github/1.3.0/data/curation/genes_evidence.tsv").open(encoding="utf-8", newline="") as stream:
        genes = {r["genes"]:r for r in csv.DictReader(stream, delimiter="\t")}
    with (ROOT/"output/palsson_proteomics_review_2026_10_06/human_protein_copy_numbers.csv").open(encoding="utf-8", newline="") as stream:
        proteins = list(csv.DictReader(stream))
    evidence = []
    for local, branch in BRANCHES.items():
        reaction = source[branch["gem_id"]]
        projected, missing, currency = project_gem(reaction, inverse)
        if missing or projected != branch["stoichiometry"]: raise ValueError("coverage column does not exactly match pinned GEM projection")
        evidence.append({"local_id": local, "GEM_reaction": reaction, "omitted_currency": currency,
            "gene_evidence": genes.get(branch["gene"]), "Deep_Red_source_rows": [r for r in proteins if r["gene"] == branch["gene"]],
            "kinetic_constants_inferred_from_protein": False, "active_in_working_ODE": False})
    citr = []
    for reaction in model["reactions"]:
        if "citr__L_c" not in reaction["metabolites"]: continue
        projected, missing, currency = project_gem(reaction, inverse)
        citr.append({"gem_id": reaction["id"], "gpr": reaction["gene_reaction_rule"], "full_stoichiometry": reaction["metabolites"],
            "missing_modeled_species": missing, "omitted_currency": currency,
            "implementable_without_new_pools": not bool(missing)})
    rhs = JointRHS(f["parameters"], f["kinetics"])
    obs = json.loads((out/"observations.json").read_text())
    policies = channel_coverage(rhs.matrix, rhs.names, obs["values"], obs["time"], actively_fitted=POOLS)
    for policy in policies:
        if policy["pool"] in ("CIT", "ECIT", "ARG", "EARG"):
            policy.update(status="missing_active_supported_branch_not_ready_for_global_fit", required_branch="VACLY" if policy["pool"] in ("CIT", "ECIT") else "VARGN")
        policy["source_normalization_status"] = "nominal_user_selected_phase_coordinates_not_author_confirmed"
    volumes = {p: volume_conservation_diagnostic(obs["values"][p], obs["values"][e], obs["time"], .58)
               for p, e in (("CIT", "ECIT"), ("ARG", "EARG"))}
    old = ROOT/d["parent_archive"]/"balances"
    old_rows = json.loads((old/"results.json").read_text())
    results = []
    for end in d["coverage_horizons"]:
        reference = next(r for r in old_rows if r["scope"] == "canonical53" and r["end_day"] == end)
        with np.load(old/f"canonical53_J{int(end)}.npz") as a: y, time, errors = a["observed"].copy(), a["time"].copy(), a["scales"].copy()
        for label, enabled in d["coverage_variants"].items():
            reactions, full = extend_matrix(rhs.names, rhs.reactions, rhs.matrix, enabled=enabled)
            m = full[[rhs.names.index(p) for p in reference["pools"]]]
            forward_names = reference["forward_direction_subset"]+enabled
            bounds = [(0., None) if r in forward_names else (None, None) for r in reactions]
            with threadpool_limits(1): result = integral_balance_screen(m, y, time, errors, reaction_bounds=bounds)
            cert = balance_certificates(m, y, time, errors, reference["pools"], [reactions.index(r) for r in forward_names])
            result.update(label=label, end_day=end, branches_enabled_in_stoichiometric_relaxation=enabled,
                branches_enabled_in_ODE=[], measured_row_rank=int(np.linalg.matrix_rank(m)), certificates=cert,
                reaction_names=reactions, forward_reactions=forward_names, pools=reference["pools"],
                rank_improvement_is_not_biological_validation=True)
            results.append(result)
            np.savez_compressed(folder/f"{label}_J{int(end)}.npz", matrix=m, observed=y, time=time, errors=errors,
                extents=np.array(result["executed_extent_integrals"]), adjustments=np.array(result["hypothetical_observation_adjustments_mM"]))
            print(f"coverage {label} J{int(end)} rank={result['measured_row_rank']} multiplier={result['minimum_working_error_multiplier']:.8g}", flush=True)
    summary = {"branch_evidence": evidence, "CITR_candidates": citr, "CITR_gene_evidence_NOS3": genes.get("NOS3"),
        "CITR_remaining_status": "blocked_dynamic_coverage_requires_new_pools_or_transport_contract",
        "CITR_gene_and_protein_evidence": {g: {"GEM_evidence": genes.get(g), "Deep_Red_rows": [r for r in proteins if r["gene"] == g],
            "absence_from_one_table_is_not_biological_absence": True} for g in ("ASL", "ASS1", "NOS3", "ANKH")},
        "channel_policies": policies, "volume_counterfactuals": volumes, "balance_relaxations": results,
        "source_values_changed": False, "initial_states_changed": False, "active_ODE_branches": [], "production_promoted": False}
    write(folder/"summary.json", summary); seal(folder)
    return summary


def probe(out_string, label, parameter, offset, resume):
    out = Path(out_string); f = verify_inputs(out); folder = out/"probes"/label
    if (folder/"files_seal.json").exists():
        if not resume: raise ValueError("completed probe; explicit resume required")
        check_seal(folder); return json.loads((folder/"result.json").read_text())
    if folder.exists(): raise ValueError("partial probe preserved; fresh successor required")
    p = f["parameters"] if parameter is None else perturb(f["parameters"], parameter, f["resolved_parameters"][parameter]["value"], offset)
    obs = json.loads((out/"observations.json").read_text())
    times, target = training_data(obs, f["design"]["horizon_day"])
    try:
        prediction, solution, rhs = predict_broad(np.array(f["initial"]), p, f["kinetics"], f["design"]["horizon_day"], times)
        diag = diagnostics(prediction, target, f["scales"])
    except (ValueError, RuntimeError, FloatingPointError) as error:
        if parameter is None: raise
        folder.mkdir(parents=True)
        row = {"label": label, "parameter": parameter, "log_offset": offset, "valid": False, "error": str(error)}
        write(folder/"result.json", row); seal(folder)
        print("invalid probe "+label+": "+str(error), flush=True)
        return row
    dense = solution.sol(np.unique(np.r_[np.linspace(1., f["design"]["horizon_day"], 301), times]))
    minimum = float(min(solution.y[:113].min(), dense[:113].min()))
    row = {"label": label, "parameter": parameter, "log_offset": offset, "predictions": prediction.tolist(), "valid": True,
        "diagnostics": diag, "minimum_checked_mM": minimum,
        "end_day": float(solution.t[-1]), "initial_exact": bool(np.array_equal(solution.y[:, 0], f["initial"])),
        "changed_parameters": [parameter] if parameter else [], "production_promoted": False}
    folder.mkdir(parents=True)
    raw, executed, factors = zip(*(rhs.rates(t, solution.sol(t)) for t in times))
    if parameter is not None:
        with np.load(out/"probes/baseline/trajectory.npz") as reference: fixed_states = reference["sample_states"].copy()
    else: fixed_states = solution.sol(times)
    fixed_raw, fixed_executed, _ = zip(*(rhs.rates(t, x) for t, x in zip(times, fixed_states.T)))
    np.savez_compressed(folder/"trajectory.npz", time=times, prediction=prediction, observed=target,
        accepted_time=solution.t, accepted_states=solution.y, sample_states=solution.sol(times),
        sample_raw_rates=np.array(raw).T, sample_executed_rates=np.array(executed).T, sample_availability=np.array(factors).T,
        fixed_state_raw_rates=np.array(fixed_raw).T, fixed_state_executed_rates=np.array(fixed_executed).T)
    write(folder/"result.json", row); seal(folder)
    print(f"probe {label} log_error={row['diagnostics']['adenylate_log_mean']:.8g}", flush=True)
    return row


def audit_one(out_string, f, selected):
    with threadpool_limits(1): return audit(Path(out_string), f, selected, f["design"]["horizon_day"])


def run(out, workers, resume):
    if (out/"manifest.json").exists(): raise ValueError("completed immutable archive")
    f = verify_inputs(out); d = f["design"]
    coverage_result = coverage(out, f)
    baseline = probe(str(out), "baseline", None, 0., resume)
    rows = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        labels = {"plus": d["log_step"], "minus": -d["log_step"], "half_plus": d["log_step"]/2, "half_minus": -d["log_step"]/2}
        jobs = [pool.submit(probe, str(out), p+"__"+direction, p, offset, resume) for p in d["parameters"] for direction, offset in labels.items()]
        for job in as_completed(jobs):
            row = job.result(); rows[row["label"]] = row
            write(out/"progress.json", {"completed_probes": len(rows)+1, "registered_probes": 1+4*len(d["parameters"])})
        obs = json.loads((out/"observations.json").read_text())
        times, target = training_data(obs, d["horizon_day"])
        columns, excluded = {}, {}
        for p in d["parameters"]:
            parts = {direction: rows[p+"__"+direction] for direction in labels}
            if not all(r["valid"] for r in parts.values()):
                excluded[p] = {key: r.get("error") for key, r in parts.items() if not r["valid"]}
                continue
            c = sensitivity_column(*(parts[key]["predictions"] for key in ("plus", "minus", "half_plus", "half_minus")), target, f["scales"], d["log_step"])
            c["directional_probes"] = {key: parts[key] for key in ("plus", "minus")}
            c["reaction_scope"] = f["parameter_scopes"][p]
            c["shared_parameter"] = len(c["reaction_scope"]) > 1
            columns[p] = c
        parent = ROOT/d["parent_archive"]
        with np.load(parent/"audits"/(d["baseline_label"]+"_J15")/"J1_J15/glut_real_candidate_ultrastrict/replay.npz") as a:
            names = a["pool_names"].tolist()
            old = a["states"][[names.index(p) for p in ADENYLATES]][:, np.searchsorted(a["time"], times)]
        current = np.array(baseline["predictions"])[[POOLS.index(p) for p in ADENYLATES]]
        noise = float(np.linalg.norm(np.log(current/old)))
        ranking, selected = select_subset(columns, baseline["diagnostics"], noise, d)
        chosen = selected[:d["original_audit_maximum_candidates"]]
        fallback = False
        if not chosen and d["fallback_audit_top_stable_effects_if_no_eligible_subset"]:
            chosen = [r for r in ranking if r["stable_two_step"] and r["above_numerical_signal"]][:d["original_audit_maximum_candidates"]]
            fallback = True
        audit_inputs = []
        for row in chosen:
            p = row["parameter"]; offset = row["direction"]*d["log_step"]
            audit_inputs.append({"label": row["probe_label"], "selected_log_factors": [offset],
                "parameters": perturb(f["parameters"], p, f["resolved_parameters"][p]["value"], offset), "glucose_kinetics": f["kinetics"]})
        audits = [job.result() for job in as_completed([pool.submit(audit_one, str(out), f, row) for row in audit_inputs])]
    valid_parameters = [p for p in d["parameters"] if p in columns]
    if not valid_parameters: raise ValueError("no valid two-step sensitivity columns")
    jac = np.column_stack([columns[p]["log_adenylate_derivative"] for p in valid_parameters])
    working = np.column_stack([columns[p]["working_derivative"] for p in valid_parameters])
    u, singular, vh = np.linalg.svd(jac, full_matrices=False)
    cosine = np.divide(jac.T@jac, np.linalg.norm(jac, axis=0)[:, None]*np.linalg.norm(jac, axis=0)[None, :],
        out=np.zeros((len(columns), len(columns))), where=(np.linalg.norm(jac, axis=0)[:, None]*np.linalg.norm(jac, axis=0)[None, :]) > 0)
    np.savez_compressed(out/"sensitivity.npz", adenylate_log_jacobian=jac, working_jacobian=working,
        singular_values=singular, right_vectors=vh, cosine=cosine, parameter_names=np.array(valid_parameters))
    original_admission, validated = {}, []
    for a in audits:
        flags = []
        folder = out/"audits"/(a["label"]+"_J15")
        for result in a["results"]:
            with np.load(folder/"J1_J15"/("glut_real_candidate_"+result["profile"])/"replay.npz") as values:
                names = values["pool_names"].tolist()
                pred = values["states"][[names.index(p) for p in POOLS]][:, np.searchsorted(values["time"], times)]
            flags.append({"profile": result["profile"], **admissibility(diagnostics(pred, target, f["scales"]), baseline["diagnostics"], d)})
        original_admission[a["label"]] = flags
        if a["numerical_pass"] and all(r["individual_adenylate_pass"] and r["protected_working_pass"] and r["gain_pass"] for r in flags):
            validated += [r for r in selected if r["probe_label"] == a["label"]]
    summary = {"baseline": baseline, "columns": columns, "excluded_columns": excluded, "ranking": ranking, "proposed_subset": selected,
        "original_admissibility": original_admission, "validated_single_levers": validated, "joint_subset_tested": False,
        "original_audit_inputs": audit_inputs, "audits": sorted(audits, key=lambda r:r["label"]),
        "audit_fallback_not_a_recommendation": fallback, "baseline_fast_original_log_discrepancy_norm": noise,
        "actual_fast_integrations": 1+len(rows), "valid_fast_integrations": 1+sum(r["valid"] for r in rows.values()),
        "singular_values": singular.tolist(),
        "local_rank_at_relative_threshold_1e-6": int(np.sum(singular > singular[0]*1e-6)) if singular[0] else 0,
        "right_vectors_are_thin_SVD_not_complete_nullspace": True,
        "all_original_audits_numerical_pass": all(a["numerical_pass"] for a in audits),
        "all_probe_minimum_checked_mM": min([baseline["minimum_checked_mM"]]+[r["minimum_checked_mM"] for r in rows.values() if r["valid"]]),
        "coverage_CITR_status": coverage_result["CITR_remaining_status"], "active_new_ODE_branches": [],
        "optimizer_run": False, "global_identifiability_proved": False, "production_promoted": False}
    write(out/"summary.json", summary); verify_inputs(out)
    write(out/"manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return {k: summary[k] for k in ("actual_fast_integrations", "proposed_subset", "all_original_audits_numerical_pass", "optimizer_run", "production_promoted")}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", type=Path); p.add_argument("--run", type=Path)
    p.add_argument("--workers", type=int, default=3); p.add_argument("--resume", action="store_true")
    a = p.parse_args()
    if bool(a.prepare) == bool(a.run) or not 1 <= a.workers <= 3: p.error("choose prepare/run and1-3 workers")
    print(json.dumps(prepare(a.prepare.resolve()) if a.prepare else run(a.run.resolve(), a.workers, a.resume), indent=2))
