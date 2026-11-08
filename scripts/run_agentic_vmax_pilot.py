"""Agent-curated matched Vmax-only searches and original ODE adjudication."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_vsam_pgk_screen import ROOT, check_seal, read, require, seal, sha, verify_inputs, verify_manifest, write, write_csv
from fla_adenylate_sensitivity import resolve_parameters
from fla_agentic_vmax_panel import compare_metrics, measure, panel_from_observations
from fla_agentic_vmax_replay import integrate_free, replay_evidence, within
from fla_agentic_vmax_search import inject_vmax_only, search_vmax
from fla_agentic_gem_correction import GEM_COMMIT, GemCorrectionRHS

CONFIG = ROOT/"config/fla_agentic_vmax_pilot.json"
PROTOCOL = ROOT/"tasks/fla_agentic_vmax_protocol_2026_11_04.md"
STRUCTURE = {"native": "native", "gem_corrected": "redox_gssg_abc"}
SOURCE_RECEIPT = ROOT/"output/b13pg_ak_source_2026_11_04/observation_identity.json"


def prepare(out):
    require(not out.exists(), "fresh successor campaign required")
    d = read(CONFIG)
    parent = ROOT/d["parent_archive"]
    p = verify_inputs(parent)
    verify_manifest(parent)
    source = read(SOURCE_RECEIPT)
    require(source["matching_numeric_cells"] == 770 and sha(ROOT/source["source"]) == source["source_sha256"], "source identity changed")
    baseline = p["cases"]["joint_half"]["parameters"]
    names = [k for group in d["groups"].values() for k in group]
    resolved = resolve_parameters(baseline, ROOT/"src/equadiff_brodbar.py", names)
    parameters = {**baseline, **{k: v["value"] for k, v in resolved.items()}}
    require(len(resolved) == 17 and len(d["groups"]) == 14 and d["fit_days"] == [4] and d["audit_days"] == [4, 8, 11, 15], "scope changed")
    require(parameters["vmax_VHK"]*d["factor_bounds"]["HK"][1] <= 5., "HK ceiling exceeded")
    require(d["network_modes"] == list(STRUCTURE), "matched structure comparison required")
    inputs = [CONFIG, PROTOCOL, Path(__file__), SOURCE_RECEIPT, ROOT/source["source"],
              ROOT/"src/fla_agentic_vmax_panel.py", ROOT/"src/fla_agentic_vmax_replay.py",
              ROOT/"src/fla_agentic_vmax_search.py", ROOT/"src/fla_agentic_gem_correction.py",
              ROOT/"qa/test_fla_agentic_vmax_panel.py", parent/"manifest.json", parent/"execution_design.json", parent/"observations.json"]
    pinned = ROOT/"output/rbc_gem_network_audit_2026_10_06"
    gem = pinned/"github/1.3.0/model/RBC-GEM.json"
    receipt = next(r for r in read(pinned/"retrieval_receipts.json") if r["file"] == gem.relative_to(pinned).as_posix())
    require(GEM_COMMIT in receipt["url"] and sha(gem) == receipt["sha256"], "GEM snapshot changed")
    inputs += [gem, pinned/"retrieval_receipts.json"]
    demand = ROOT/"output/agentic_atp_demand_2026_11_04"
    check_seal(demand)
    proposed = read(demand/"priority_vmax_groups.json")["groups"]
    starts = []
    for row in proposed:
        keys = {p["key"] for p in row["parameters"]}
        group = next((name for name, members in d["groups"].items() if set(members) == keys), None)
        require(group is not None, f"agent proposal not representable: {row['id']}")
        factor = min(row["suggested_multipliers"])
        require(d["factor_bounds"][group][0] <= factor <= d["factor_bounds"][group][1], "agent seed outside box")
        starts.append({group: factor})
    starts += [{"GAPDH": 1.5, "AK": .5}, {"PGM_ENO": 1.5, "PEPase": .5, "LDH": 1.5, "AK": .5}]
    agent_paths = sorted(demand.glob("*.json"))
    inputs += agent_paths
    initial, obs = p["initial"], read(parent/"observations.json")
    source_profiles = p["design"]["profiles"]
    references = {}
    for profile in source_profiles:
        path = parent/"J1_J46"/f"glut_real_candidate_{profile}"/"replay.npz"
        with np.load(path) as a:
            t, names0 = a["time"], a["pool_names"].tolist()
            days = np.searchsorted(t, d["audit_days"])
            require(np.array_equal(t[days], d["audit_days"]) and np.array_equal(a["accepted_states"][:, 0], initial) and
                    all(initial[names0.index(k)] == y[0] for k, y in obs["values"].items()), "exact J1 or source support changed")
            references[profile] = a["states"][[names0.index(k) for k in obs["values"]]][:, days].tolist()
    f = {"design": d, "initial": initial, "parameters": parameters, "kinetics": p["kinetics"], "numeric": p["numeric"],
         "structure_modes": STRUCTURE, "GEM_commit": GEM_COMMIT, "resolved_capacities": resolved,
         "reference_predictions": references, "source_identity": source, "seed_starts": starts,
         "agent_evidence": [x.relative_to(ROOT).as_posix() for x in agent_paths],
         "input_sha256": {x.relative_to(ROOT).as_posix(): sha(x) for x in [*inputs, *(ROOT/key for key in p["input_sha256"])]}}
    out.mkdir(parents=True)
    write(out/"execution_design.json", f)
    write(out/"observations.json", obs)
    write(out/"source_seal.json", {x: sha(out/x) for x in ("execution_design.json", "observations.json")})
    return f


def rhs_for(f, parameters, network, backend="joint"):
    n = f["numeric"]
    return GemCorrectionRHS(parameters, f["kinetics"], mode=f["structure_modes"][network], backend=backend,
                            hematocrit=n["hematocrit"], threshold=n["availability_threshold_mM"])


def parameters_for(f, x):
    p = inject_vmax_only(f["parameters"], f["design"]["groups"], x)
    allowed = set(f["resolved_capacities"])
    require({k for k in p if p[k] != f["parameters"][k]} <= allowed and p["vmax_VHK"] <= 5., "non-Vmax or forbidden HK change")
    return p


def pareto(rows):
    front, best = [], np.inf
    for r in sorted(rows, key=lambda r: (r["adenylate_loss"], r["other_loss"], r["evaluation_id"])):
        if r["other_loss"] < best:
            front.append(r)
            best = r["other_loss"]
    return front


def search_network(out, f, obs, network):
    d = f["design"]
    folder = out/"search"/network
    folder.mkdir(parents=True)
    panel = panel_from_observations(obs, d["fit_days"], d)
    reference = measure(np.array(f["reference_predictions"]["ultrastrict"])[:, :1], panel)
    limits = {k: np.log(d["factor_bounds"][k]).tolist() for k in d["groups"]}
    starts = [[float(np.log(row.get(k, 1.))) for k in d["groups"]] for row in f["seed_starts"]]

    def evaluate(x):
        p = parameters_for(f, x)
        rhs = rhs_for(f, p, network)
        sol, _, _, minimum = integrate_free(rhs, f["initial"], 4, d["fit_days"], d["fit_profile"], f["numeric"]["negative_tolerance_mM"])
        m = measure(sol.sol(d["fit_days"])[[rhs.names.index(k) for k in panel["names"]]], panel)
        return {**compare_metrics(m, reference, panel, d), "metrics": m, "minimum_checked_mM": minimum}

    with threadpool_limits(1), (folder/"trace.jsonl").open("x", encoding="utf-8") as stream:
        def progress(row):
            stream.write(json.dumps(row, allow_nan=False)+"\n")
            stream.flush()
            if row["source"] == "evaluation" and row["evaluation_id"] % 16 == 0:
                print(f"{network}: {row['evaluation_id']}/{d['budget_per_network']} evaluations", flush=True)
        result = search_vmax(evaluate, limits, budget=d["budget_per_network"], seed=d["seed"], starts=starts,
                             on_probe=progress, explore_infeasible=True)
    all_valid = result["ranked_feasible"]+result["ranked_infeasible"]
    require(all_valid, f"{network}: no valid integrations")
    eligible = [r for r in result["ranked_feasible"] if r["callback_result"]["sufficient_gain"]]
    front = pareto(all_valid)
    if eligible:
        finalist, role = eligible[0], "fit_guard_eligible"
    else:
        improved = [r for r in front if r["callback_result"]["sufficient_gain"]]
        finalists = improved or front
        finalist = min(finalists, key=lambda r: (max(r["adenylate_loss"], r["other_loss"]),
                                                 r["max_guard_excess"], r["evaluation_id"]))
        role = "diagnostic_Pareto_tradeoff_not_guard_eligible"
    result.update(network=network, structure=f["structure_modes"][network], finalist=finalist,
                  finalist_role=role, all_valid_pareto=front,
                  most_adenylate_improvement=min(all_valid, key=lambda r: r["adenylate_loss"]),
                  sufficient_gain_guard_eligible_count=len(eligible))
    write(folder/"result.json", result)
    seal(folder)
    return {"network": network, "evaluations": result["actual_evaluations"], "eligible": len(eligible),
            "finalist_evaluation_id": finalist["evaluation_id"], "finalist_role": role}


def full_audit(out, f, obs, network, profile, vector):
    p = parameters_for(f, vector)
    full, fast = rhs_for(f, p, network, "full"), rhs_for(f, p, network)
    d, n = f["design"], f["numeric"]
    folder = out/"audits"/network/profile
    folder.mkdir(parents=True)
    with threadpool_limits(1):
        arrays, stats = replay_evidence(full, f["initial"], 15, d["audit_days"], n["numerical_profiles"][profile],
                                        n, lambda t, x: fast.rates(t, x)[:2])
    names = arrays["pool_names"].tolist()
    indices = np.searchsorted(arrays["time"], d["audit_days"])
    require(np.array_equal(arrays["time"][indices], d["audit_days"]), "source sample times changed")
    selected = arrays["states"][[names.index(k) for k in obs["values"]]][:, indices]
    metrics, csv_rows = {}, []
    for label, ix in (("fit_J4", [0]), ("check_J8_J15", [1, 2, 3])):
        panel = panel_from_observations(obs, [d["audit_days"][i] for i in ix], d)
        current = measure(selected[:, ix], panel)
        base = measure(np.array(f["reference_predictions"][profile])[:, ix], panel)
        comparison = compare_metrics(current, base, panel, d)
        metrics[label] = {**comparison, "metrics": current, "reference": base}
        csv_rows.extend([network, profile, label, k, float(current["RMSE_mM"][i]), float(base["RMSE_mM"][i]),
                         k in comparison["off_target_failures"]] for i, k in enumerate(panel["names"]))
    reactions = arrays["reactions"].tolist()
    h = arrays["matrix"][names.index("ATP")]+.5*arrays["matrix"][names.index("ADP")]
    budgets = {r: float(h[i]*arrays["executed8"][i].sum()) for i, r in enumerate(reactions)}
    write(folder/"result.json", {**stats, "network": network, "profile": profile, "periods": metrics, "J1_J15_H_by_reaction_mM": budgets})
    write_csv(folder/"all55.csv", ["network", "profile", "period", "pool", "candidate_RMSE_mM", "reference_RMSE_mM", "guard_failed"], csv_rows)
    np.savez_compressed(folder/"replay.npz", **arrays)
    seal(folder)
    print(f"{network} {profile} original J15 replay: numeric={stats['numerical_pass']}", flush=True)
    return stats


def search_all(out):
    f = prepare(out)
    obs = read(out/"observations.json")
    print(f"Frozen matched agentic Vmax pilot: {f['design']['budget_per_network']} attempts per network, J4 only", flush=True)
    with ProcessPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(search_network, out, f, obs, label) for label in STRUCTURE]
        rows = [job.result() for job in as_completed(jobs)]
    verify_inputs(out)
    write(out/"search_summary.json", rows)
    return rows


def audit_all(out):
    require(not (out/"manifest.json").exists() and not (out/"audits").exists(), "audit requires a completed fresh search")
    f, obs = verify_inputs(out), read(out/"observations.json")
    search = {}
    for mode in STRUCTURE:
        check_seal(out/"search"/mode)
        search[mode] = read(out/"search"/mode/"result.json")
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(full_audit, out, f, obs, mode, profile, result["finalist"]["log_factors"])
                for mode, result in search.items() for profile in ("strict", "ultrastrict")]
        for job in as_completed(jobs):
            job.result()
    summary = {}
    for mode, s in search.items():
        base = out/"audits"/mode
        replay, cross = {}, []
        for profile in ("strict", "ultrastrict"):
            check_seal(base/profile)
            replay[profile] = read(base/profile/"result.json")
        with np.load(base/"strict/replay.npz") as a, np.load(base/"ultrastrict/replay.npz") as b:
            require(np.array_equal(a["time"], b["time"]), "cross-tolerance grid differs")
            cross = [within(a[k], b[k], f["numeric"], "comparison") for k in ("states", "raw8", "executed8")]
        numeric = bool(all(v.all() for v in cross) and all(x["numerical_pass"] for x in replay.values()))
        admitted = bool(numeric and s["finalist_role"] == "fit_guard_eligible" and
                        all(r["guards_pass"] and r["sufficient_gain"] for p in replay.values() for r in p["periods"].values()))
        summary[mode] = {"numerical_pass": numeric, "cross_checks": sum(int(v.sum()) for v in cross),
                         "cross_checks_total": sum(v.size for v in cross), "J15_admitted": admitted, "profiles": replay,
                         "finalist_role": s["finalist_role"], "finalist_evaluation_id": s["finalist"]["evaluation_id"],
                         "parameters": parameters_for(f, s["finalist"]["log_factors"])}
    write(out/"validation_summary.json", {"networks": summary, "production_promoted": False,
          "biological_calibration": False, "historically_exposed_checks_not_blind": True, "Km_changed": False})
    verify_inputs(out)
    write(out/"manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return {k: {"numerical_pass": v["numerical_pass"], "J15_admitted": v["J15_admitted"]} for k, v in summary.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    print(audit_all(args.out.resolve()) if args.audit else search_all(args.out.resolve()))
