"""Matched objective comparison, explicit observation contract and interval readiness."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_calibration_observations import fixed_error_scales, objective_metrics, validate_series
from fla_balance_feasibility import integral_balance_screen
from fla_hk_pfk_split import unpack, coordinate_bounds, predict_broad, training_data, POOLS
from fla_profiled_observation_noise import profile_lognormal_dispersion
from fla_joint_calibration import JointRHS
from run_protected_joint import verify_inputs, seal, check_seal
from run_glut_only_free_replay import write, sha
from run_broad_protected_joint import audit

CONFIG = ROOT/"config/fla_objective_reformulation.json"


def scale_contract(target, design, pair=None):
    a, b = pair or (design["absolute_scale_fraction"], design["relative_scale_fraction"])
    return fixed_error_scales(target, absolute_fraction=a, relative_fraction=b, interpretation=design["scale_interpretation"])


def prepare(out):
    from verify_hk_pfk_split import verify
    if out.exists(): raise ValueError("fresh reformulation archive required")
    d = json.loads(CONFIG.read_text())
    parent = ROOT/d["parent_archive"]
    with threadpool_limits(1): evidence = verify(parent)
    previous = json.loads((parent/"execution_design.json").read_text())
    chosen = json.loads((parent/"summary.json").read_text())["selected"]
    obs = json.loads((parent/"observations.json").read_text())
    f = {key: copy.deepcopy(previous[key]) for key in ("parent_design", "parameters", "kinetics", "initial", "guards",
         "primitive_capacities", "primitive_factor_bounds", "seed_log_investment")}
    f.update(design=d, parent_verification=evidence, starts={"restored": [previous["seed_log_investment"]]*2,
        "split": chosen["selected_log_factors"]}, phases={})
    rhs = JointRHS(f["parameters"], f["kinetics"])
    series = []
    for i, p in enumerate(POOLS):
        ext = rhs.volumes[rhs.names.index(p)] != .58
        row = {"channel_id": "local_Sheet1:"+p, "metabolite": p,
            "trajectory_id": "local_Sheet1_unresolved_cohort", "cohort_id": "local_workbook_not_assigned_to_JBC_donors",
            "source_id": "src/Data_Bordbar_et_al_exp.xlsx:Sheet1", "donor_id": None, "donor_identity_status": "unresolved",
            "compartment": "extracellular" if ext else "intracellular", "volume_basis": "supernatant_phase" if ext else "cell_phase",
            "measurement_type": "absolute_concentration", "unit": "mM", "normalization_status": "resolved",
            "source_normalization_provenance": "user_selected_nominal_phase_coordinates_not_author_confirmed",
            "time": obs["time"], "values": obs["values"][p]}
        series.append(validate_series(row))
    for end in (10., 15.):
        times, target = training_data(obs, end)
        f["phases"][str(int(end))] = {"times": times.tolist(), "scales": scale_contract(target, d)}
    paths = [CONFIG, Path(__file__), ROOT/"src/fla_calibration_observations.py", ROOT/"src/fla_balance_feasibility.py",
        ROOT/"qa/test_fla_objective_reformulation.py", ROOT/"scripts/verify_fla_objective_reformulation.py",
        parent/"execution_design.json", parent/"observations.json", parent/"summary.json", parent/"manifest.json"]
    paths += [ROOT/p for p in previous["input_sha256"]]
    f["input_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    out.mkdir(parents=True)
    write(out/"execution_design.json", f); write(out/"observations.json", obs)
    write(out/"observation_contract.json", {"series": series, "scale_type": d["scale_interpretation"],
        "relative_observation_operators_tested_not_experimental_relative_calibration": True,
        "different_cohorts_are_not_merged": True, "unknown_donors_are_not_fabricated": True})
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json", "observation_contract.json")})
    return {"prepared": True, "parent_checks": evidence["checks"], "J10_values": 22, "J15_values": 44,
        "old13_guards": "diagnostics_only", "measurement_scales": "engineering_not_assay_uncertainty"}


def balances(out, f):
    folder = out/"balances"
    if (folder/"files_seal.json").exists():
        check_seal(folder); return json.loads((folder/"results.json").read_text())
    if folder.exists(): raise ValueError("partial balance screen preserved; successor required")
    folder.mkdir()
    obs = json.loads((out/"observations.json").read_text())
    rhs = JointRHS(f["parameters"], f["kinetics"])
    results = []
    for end in f["design"]["balance_horizons"]:
        time = np.array(obs["time"]); use = time <= end
        for scope in f["design"]["balance_channel_scopes"]:
            pools = list(POOLS) if scope == "eleven_training" else [p for p in obs["values"] if p not in ("B13PG", "P2G")]
            y = np.array([obs["values"][p] for p in pools])[:, use]
            # Zero-only channels remain exact nominal zeros in this relaxation.
            median = np.median(y[:, 1:], axis=1)
            positive_initial = y[:, 0]
            scale = np.where(median > 0, median, positive_initial)
            zero_only = [p for p, v in zip(pools, scale) if v <= 0]
            errors = f["design"]["absolute_scale_fraction"]*scale[:, None]+f["design"]["relative_scale_fraction"]*y
            m = rhs.matrix[[rhs.names.index(p) for p in pools]]
            bounds = [(0., None) if r in f["design"]["forward_direction_subset"] else (None, None) for r in rhs.reactions]
            with threadpool_limits(1): result = integral_balance_screen(m, y, time[use], errors, reaction_bounds=bounds)
            result.update(end_day=end, scope=scope, pools=pools, time=time[use].tolist(),
                working_error_scales_mM=errors.tolist(), forward_direction_subset=f["design"]["forward_direction_subset"],
                other_directions="optimistically_signed", reaction_names=rhs.reactions,
                exact_nominal_zero_channels=zero_only, zero_policy="no_assay_limit_inferred_no_positive_floor_added",
                interpretation="necessary_balance_relaxation_not_full_kinetic_feasibility")
            np.savez_compressed(folder/f"{scope}_J{int(end)}.npz", matrix=m, observed=y, time=time[use], scales=errors,
                                extents=np.array(result["executed_extent_integrals"]), adjustments=np.array(result["hypothetical_observation_adjustments_mM"]))
            results.append(result)
            write(folder/"results.json", results)
            print(f"balance {scope} J{int(end)} exact={result['exact_measured_balances_feasible']} multiplier={result['minimum_working_error_multiplier']:.8g}", flush=True)
    seal(folder)
    return results


def legacy_diagnostics(prediction, target, guards):
    rmse = np.sqrt(np.mean((prediction-target)**2, axis=1))
    errors = np.r_[rmse, np.abs(prediction[POOLS.index("PEP")]-target[POOLS.index("PEP")])]
    limits = np.array(guards["fit_limits_mM"])
    score = (profile_lognormal_dispersion(prediction.ravel(), target.ravel())
             if np.all(prediction > 0) and np.any(prediction != target) else None)
    return {"passed": bool(np.all(errors <= limits)), "errors_mM": errors.tolist(), "RMSE_mM": dict(zip(POOLS, rmse.tolist())),
        "score": score, "lognormal_defined": score is not None, "used_as_search_constraints": False}


def evaluate(x, f, end, loss, times, target):
    p, k, factors = unpack(x, f, "split")
    pred, solution, _ = predict_broad(np.array(f["initial"]), p, k, end, times)
    early = times <= 10
    legacy = legacy_diagnostics(pred[:, early], target[:, early], f["guards"])
    metrics = objective_metrics(pred, target, f["phases"][str(int(end))]["scales"])
    if loss == "lognormal" and legacy["score"] is None: raise ValueError("lognormal objective undefined at zero prediction")
    value = (legacy["score"]["negative_log_likelihood"] if loss == "lognormal" else
             metrics["balanced_MSE"] if loss == "normalized" else metrics["worst_channel_MSE"])
    return {"valid": True, "log_factors": np.asarray(x).tolist(), "factors": factors, "predictions": pred.tolist(),
        "objective_value": value, "metrics": metrics, "legacy13": legacy}, solution


def fit_one(out_string, label, loss, start, end, resume):
    out = Path(out_string); f = verify_inputs(out)
    folder = out/"fits"/label
    if (folder/"files_seal.json").exists():
        if not resume: raise ValueError("completed fit; explicit resume required")
        check_seal(folder); return json.loads((folder/"result.json").read_text())
    if folder.exists() and not resume: raise ValueError("partial fit requires explicit resume")
    folder.mkdir(parents=True, exist_ok=True)
    times, target = training_data(json.loads((out/"observations.json").read_text()), end)
    path = folder/"trace.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    cache = {tuple(r["log_factors"]): r for r in rows}
    bounds = coordinate_bounds(f, "split")
    options = f["design"]["optimizer"]
    class BudgetStop(Exception): pass
    def get(x):
        key = tuple(float(v) for v in x)
        if key in cache: return cache[key]
        if len(rows) >= options["actual_call_cap"]: raise BudgetStop
        try: row, _ = evaluate(np.array(x), f, end, loss, times, target)
        except (ValueError, RuntimeError, FloatingPointError) as error:
            row = {"valid": False, "log_factors": list(key), "error": str(error)}
        row["call"] = len(rows)+1
        rows.append(row); cache[key] = row
        with path.open("a", encoding="utf-8") as stream: stream.write(json.dumps(row, allow_nan=False)+"\n"); stream.flush()
        if len(rows) % 10 == 0:
            best = min((r for r in rows if r["valid"]), key=lambda r:r["objective_value"])
            print(f"{label} calls={len(rows)} best={best['objective_value']:.9g}", flush=True)
        return row
    def values(x):
        r = get(x)
        return (r["objective_value"], np.array(r["metrics"]["channel_MSE"])) if r["valid"] else (1e12, np.full(11, 1e12))
    derivative_cache = {}
    def derivatives(x):
        key = tuple(x)
        if key not in derivative_cache:
            base, per = values(x)
            gradient, jac = np.zeros(2), np.zeros((11, 2))
            for j in range(2):
                h = options["difference_step"] if x[j]+options["difference_step"] <= bounds[j, 1] else -options["difference_step"]
                other = np.array(x); other[j] += h
                val, channel = values(other)
                gradient[j], jac[:, j] = (val-base)/h, (channel-per)/h
            derivative_cache[key] = gradient, jac
        return derivative_cache[key]
    seed = np.array(start)
    if not get(seed)["valid"]: raise ValueError("invalid declared starting ODE")
    if resume and len(rows) > 1: seed = np.array(min((r for r in rows if r["valid"]), key=lambda r:r["objective_value"])["log_factors"])
    success, message, terminal = False, "not_started", seed
    try:
        if loss == "minimax":
            x0 = np.r_[seed, max(values(seed)[1])]
            sol = minimize(lambda u: u[2], x0, jac=lambda u: np.array([0., 0., 1.]), method="SLSQP",
                bounds=[*bounds, (0., None)], constraints=[{"type": "ineq", "fun": lambda u:u[2]-values(u[:2])[1],
                    "jac": lambda u: np.column_stack([-derivatives(u[:2])[1], np.ones(11)])}],
                options={"maxiter": options["maxiter"], "ftol": options["ftol"]})
            terminal = sol.x[:2]
        else:
            sol = minimize(lambda x:values(x)[0], seed, jac=lambda x:derivatives(x)[0], method="SLSQP", bounds=bounds,
                           options={"maxiter": options["maxiter"], "ftol": options["ftol"]})
            terminal = sol.x
        success, message = bool(sol.success), str(sol.message)
    except BudgetStop: message = "actual_objective_budget_exhausted_not_convergence"
    best = min((r for r in rows if r["valid"]), key=lambda r:r["objective_value"])
    replay, solution = evaluate(best["log_factors"], f, end, loss, times, target)
    p, k, factors = unpack(best["log_factors"], f, "split")
    np.savez_compressed(folder/"fit_replay.npz", sample_time=times, observed=target, prediction=np.array(replay["predictions"]),
        accepted_time=solution.t, accepted_states=solution.y)
    result = {"label": label, "loss": loss, "end_day": end, "selected_log_factors": best["log_factors"],
        "terminal_log_factors": terminal.tolist(), "parameters": p, "glucose_kinetics": k, "factors": factors,
        "actual_objective_integrations": len(rows), "optimizer_success": success, "optimizer_message": message,
        "objective_value": replay["objective_value"], "metrics": replay["metrics"], "legacy13": replay["legacy13"],
        "legacy13_used_to_filter_selection": False, "production_promoted": False}
    write(folder/"result.json", result); seal(folder)
    print(f"{label} done calls={len(rows)} success={success} value={result['objective_value']:.9g}", flush=True)
    return result


def audit_one(out_string, f, selected, end):
    with threadpool_limits(1): return audit(Path(out_string), f, selected, end)


def run(out, workers, resume):
    if (out/"manifest.json").exists(): raise ValueError("completed immutable campaign")
    f = verify_inputs(out)
    balance = balances(out, f)
    fits = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(fit_one, str(out), f"J10_{loss}_{name}", loss, start, 10., resume)
                for loss in f["design"]["losses"] for name, start in f["starts"].items()]
        for job in as_completed(jobs): fits.append(job.result())
        selected10 = [min((r for r in fits if r["loss"] == loss), key=lambda r:r["objective_value"]) for loss in f["design"]["losses"]]
        ready = next(r for r in balance if r["scope"] == "eleven_training" and r["end_day"] == 15)["minimum_working_error_multiplier"] <= 1
        selected15 = []
        if ready and f["design"]["automatic_J15_fit"]:
            jobs = [pool.submit(fit_one, str(out), "J15_"+r["loss"], r["loss"], r["selected_log_factors"], 15., resume)
                    for r in selected10 if r["loss"] in f["design"]["J15_losses"]]
            for job in as_completed(jobs): selected15.append(job.result())
            fits.extend(selected15)
        # Original-path guards are reported, never used as hidden new acceptance caps.
        audit_jobs = [pool.submit(audit_one, str(out), f, row, end) for row in selected10 for end in (10.,)]
        for row in selected15: audit_jobs += [pool.submit(audit_one, str(out), f, row, end) for end in (15., 46.)]
        if not selected15:
            audit_jobs += [pool.submit(audit_one, str(out), f, row, 46.) for row in selected10]
        audits = [job.result() for job in as_completed(audit_jobs)]
    fits.sort(key=lambda r:r["label"]); audits.sort(key=lambda r:(r["label"], r["end_day"]))
    numerical = all(a["numerical_pass"] for a in audits)
    summary = {"fits": fits, "selected_J10": selected10, "selected_J15": selected15, "audits": audits,
        "J15_balance_gate_passed": ready, "J15_skipped_reason": None if selected15 else "declared_necessary_balance_gate_or_configuration",
        "all_original_numerical_checks_passed": numerical, "legacy13_are_diagnostics_only": True,
        "actual_objective_integrations": sum(r["actual_objective_integrations"] for r in fits),
        "new_initialization_or_kinetics_outside_HK_PFK": False, "production_promoted": False,
        "biological_accuracy_established": False, "relative_experimental_data_fitted": False}
    write(out/"summary.json", summary); verify_inputs(out)
    write(out/"manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return {k: summary[k] for k in ("actual_objective_integrations", "J15_balance_gate_passed", "all_original_numerical_checks_passed", "production_promoted")}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", type=Path); p.add_argument("--run", type=Path)
    p.add_argument("--workers", type=int, default=3); p.add_argument("--resume", action="store_true")
    a = p.parse_args()
    if bool(a.prepare) == bool(a.run) or not 1 <= a.workers <= 3: p.error("choose prepare/run and1-3 workers")
    print(json.dumps(prepare(a.prepare.resolve()) if a.prepare else run(a.run.resolve(), a.workers, a.resume), indent=2))
