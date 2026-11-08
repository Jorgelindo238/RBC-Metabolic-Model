"""Matched, unforced J1-J46 replay of the sealed VSAM/PGK half-step."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_vsam_pgk_screen import (ROOT, ADENYLATES, check_seal, guard, read, require,
                                 score, seal, sha, verify_inputs, verify_manifest, write, write_csv)
from run_glut_only_free_replay import case_options, close, replay
from rbc_glut_only_transport import equadiff_glut_only
from fla_joint_calibration import JointRHS

SCREEN = ROOT / "output/vsam_pgk_screen_2026_11_04"
VALIDATION = ROOT / "output/vsam_pgk_screen_validation_2026_11_04"
PROTOCOL = ROOT / "tasks/fla_vsam_pgk_j46_protocol_2026_11_04.md"
END = 46


def periods(days):
    days = np.asarray(days)
    require(days.ndim == 1 and len(days) == 14 and days[0] == 1 and days[-1] == END
            and np.all(np.diff(days) > 0), "expected the complete original time support")
    return {"J4_J15": (days > 1) & (days <= 15), "J18_J46": days > 15, "J4_J46": days > 1}


def prepare(out):
    require(not out.exists(), "use a fresh successor archive")
    f = verify_inputs(SCREEN)
    verify_manifest(SCREEN)
    check_seal(VALIDATION)
    export = read(VALIDATION/"conditional_replay_candidate.json")
    require(export["source_manifest_sha256"] == sha(SCREEN/"manifest.json") and
            export["label"] == read(SCREEN/"summary.json")["conditional_joint_candidate"] == "joint_half" and
            not export["J46_replayed"] and not export["production_promoted"], "candidate provenance mismatch")
    p0, p1 = (f["cases"][label]["parameters"] for label in ("baseline", "joint_half"))
    require({**p0, **export["kinetic_overrides"]} == p1 and
            set(export["kinetic_overrides"]) == {"vmax_VSAM", "vmax_VPGK"}, "more than two changes")
    reference = ROOT/f["reuse"]["baseline"]
    baseline = reference.with_name("J15_normalized_J46")
    check_seal(baseline)
    require(read(baseline/"audit_summary.json")["numerical_pass"], "reference J46 audit not valid")
    original = baseline.parents[1]/"fits/J15_normalized/result.json"
    require(read(original)["parameters"] == p0 and read(original)["glucose_kinetics"] == f["kinetics"], "reference parameter mismatch")
    numeric_source = ROOT/f["parent_design"]["source_archive"]/"execution_design.json"
    numeric = read(numeric_source)["design"]
    require(numeric["numerical_profiles"] == f["parent_design"]["numerical_profiles"], "tolerance mismatch")
    numeric["cases"] = ["glut_real_candidate"]
    obs = read(SCREEN/"observations.json")
    require(len(obs["values"]) == 55, "expected every source channel")
    numeric["guard_pools"] = list(obs["values"])
    paths = [Path(__file__), PROTOCOL, ROOT/"qa/test_vsam_pgk_j46.py", numeric_source, original, baseline/"files_seal.json",
             SCREEN/"manifest.json", SCREEN/"summary.json", SCREEN/"execution_design.json", SCREEN/"observations.json",
             VALIDATION/"files_seal.json", VALIDATION/"conditional_replay_candidate.json", VALIDATION/"verification.json"]
    f.update(end_day=END, numeric=numeric, baseline_J46=baseline.relative_to(ROOT).as_posix(),
             input_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in [*paths, *(ROOT/p for p in f["input_sha256"])]})
    out.mkdir(parents=True)
    write(out/"execution_design.json", f)
    write(out/"observations.json", obs)
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return f, obs


def one_profile(out, f, obs, profile):
    candidate = {"glucose_kinetics": f["kinetics"]}
    with threadpool_limits(1):
        result, _ = replay(out, "glut_real_candidate", profile, END, np.array(f["initial"]),
                           f["cases"]["joint_half"]["parameters"], candidate, f["kinetics"], f["numeric"],
                           np.array(obs["time"]), {p: np.array(y) for p, y in obs["values"].items()})
    return result


def run(out):
    f, obs = prepare(out)
    print("Frozen J1-J46 replay: two original profiles, no fitting or forcing", flush=True)
    with ProcessPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(one_profile, out, f, obs, profile) for profile in f["design"]["profiles"]]
        results = [job.result() for job in jobs]
    verify_inputs(out)
    write(out/"run_summary.json", {"profiles": results, "new_ODE_integrations": 2, "optimizer_run": False})
    write(out/"manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return {"completed_profiles": [r["profile"] for r in results], "profile_checks_pass": all(r["numerical_pass"] for r in results)}


def inspect_replay(folder, f, obs, label, profile, counts):
    path = folder/f"J1_J{END}"/f"glut_real_candidate_{profile}"
    evidence = read(path/"result.json")
    n = f["numeric"]
    p = f["cases"][label]["parameters"]
    rhs = JointRHS(p, f["kinetics"])
    options = case_options("glut_real_candidate", {"glucose_kinetics": f["kinetics"]}, f["kinetics"], n, p)
    with np.load(path/"replay.npz") as a:
        names, reactions = a["pool_names"].tolist(), a["reactions"].tolist()
        m, time, states, cuts = (a[k] for k in ("matrix", "time", "states", "boundaries"))
        require(names == list(rhs.names) and reactions == list(rhs.reactions) and np.array_equal(m, rhs.matrix), "network changed")
        require(np.array_equal(a["initial"], f["initial"]) and np.array_equal(a["accepted_states"][:, 0], f["initial"])
                and all(f["initial"][names.index(p)] == v[0] for p, v in obs["values"].items()), "J1 changed")
        ix, dc = np.searchsorted(time, obs["time"]), np.searchsorted(time, cuts)
        require(np.array_equal(time[ix], obs["time"]) and np.array_equal(time[dc], cuts), "nonoriginal observation or balance time")
        sampled = states[[names.index(p) for p in obs["values"]]][:, ix]
        integral = {}
        minimum = min(states[:113].min(), a["accepted_states"][:113].min())
        for order in (4, 8):
            cells, weights, x = (a[f"q{order}_{key}"] for key in ("intervals", "weights", "states"))
            minimum = min(minimum, x[:113].min())
            for kind in ("raw", "executed"):
                rates = a[f"q{order}_{kind}_rates"]
                result = np.array([np.bincount(cells, weights=weights*v, minlength=45) for v in rates])
                require(close(result, a[f"{kind}{order}"], n, "quadrature").all(), "quadrature reconstruction changed")
                integral[order, kind] = result
                if order == 8 and kind == "executed":
                    executed_rates = rates
        nodes, raw_rates = a["q8_nodes"], a["q8_raw_rates"]
        for j in np.linspace(0, len(nodes)-1, 9).astype(int):
            live = {}
            derivative = equadiff_glut_only(nodes[j], x[:, j], numerical_audit=live, **options)
            require(np.array_equal(derivative[:113], m@executed_rates[:, j]) or
                    np.max(np.abs(derivative[:113]-m@executed_rates[:, j])) <= n["closure_atol_mM_per_day"], "live balance mismatch")
            require(np.array_equal([live["raw_fluxes"][r] for r in reactions], raw_rates[:, j]) and
                    np.array_equal([live["effective_fluxes"][r] for r in reactions], executed_rates[:, j]), "live rate/parameter mismatch")
            counts["live_rate_checkpoints"] += 1
        tests = {"daily_balances": close(np.diff(states[:113, dc]), m@integral[8, "executed"], n, "quadrature"),
                 **{k+"_quadrature": close(integral[4, k], integral[8, k], n, "quadrature") for k in ("raw", "executed")}}
        for k, v in tests.items():
            counts[k] += int(v.sum()) if label == "joint_half" else 0
        valid = bool(all(v.all() for v in tests.values()) and minimum >= n["negative_tolerance_mM"] and
                     max(evidence["raw_closure_max"], evidence["executed_closure_max"]) <= n["closure_atol_mM_per_day"])
        require(valid == evidence["numerical_pass"], "profile numerical flag mismatch")
        budgets = {}
        for period, include in (("J1_J15", nodes < 15), ("J15_J46", nodes > 15), ("J1_J46", np.ones(len(nodes), bool))):
            budgets[period] = {}
            for name in ADENYLATES:
                terms = m[names.index(name), :, None] * executed_rates[:, include]
                w = weights[include]
                budgets[period][name] = {"production_mM": float(np.maximum(terms, 0).sum(axis=0)@w),
                                         "consumption_mM": float(-np.minimum(terms, 0).sum(axis=0)@w),
                                         "net_by_reaction_mM": dict(zip(reactions, (terms@w).tolist()))}
        return {"numerical_pass": valid, "minimum_checked_mM": float(minimum), "sampled_mM": sampled.tolist(),
                "executed_adenylate_budgets": budgets}, (states[:113], integral[8, "raw"], integral[8, "executed"])


def compare(out, report):
    require(not report.exists() and not report.is_relative_to(out), "fresh separate comparison directory required")
    verify_manifest(out)
    f, obs = verify_inputs(out), read(out/"observations.json")
    base = ROOT/f["baseline_J46"]
    check_seal(base)
    d = f["design"]
    pools, days = list(obs["values"]), np.array(obs["time"])
    target = np.array(list(obs["values"].values()))
    masks = periods(days)
    bands = d["absolute_scale_fraction"]*np.median(target[:, masks["J4_J15"]], axis=1)[:, None]+d["relative_scale_fraction"]*target
    require((bands > 0).all(), "zero scale would require a declared detection limit")
    counts = {k: 0 for k in ("daily_balances", "raw_quadrature", "executed_quadrature", "cross_tolerance", "live_rate_checkpoints")}
    cases, cross = {}, {}
    for label, folder in (("baseline", base), ("joint_half", out)):
        cases[label], pair = {}, []
        for profile in d["profiles"]:
            cases[label][profile], arrays = inspect_replay(folder, f, obs, label, profile, counts)
            pair.append(arrays)
        checks = [close(a, b, f["numeric"], "comparison") for a, b in zip(*pair)]
        cross[label] = bool(all(v.all() for v in checks))
        if label == "joint_half":
            counts["cross_tolerance"] = sum(int(v.sum()) for v in checks)
    rows, samples, decisions = [], [], {}
    for profile in d["profiles"]:
        reference, candidate = (np.array(cases[label][profile]["sampled_mM"]) for label in ("baseline", "joint_half"))
        decisions[profile] = {}
        for k, mask in masks.items():
            metrics = [score(x[:, mask], target[:, mask], bands[:, mask], pools) for x in (reference, candidate)]
            result = guard(metrics[1], metrics[0], pools, days[mask].tolist(), d)
            decisions[profile][k] = {"guards": result, "baseline_metrics": metrics[0], "joint_metrics": metrics[1]}
            for i, name in enumerate(pools):
                b, c = (m["RMSE_mM"][i] for m in metrics)
                rows.append([profile, k, name, name in ("B13PG", "P2G"), b, c, c-b, name in result["all55_failures"]])
        for i, name in enumerate(pools):
            for j, day in enumerate(days):
                samples.append([profile, name, day, target[i,j], reference[i,j], candidate[i,j]])
    numeric = bool(all(cross.values()) and all(r["numerical_pass"] for case in cases.values() for r in case.values()))
    retained = bool(numeric and all(r["guards"]["pass"] for windows in decisions.values() for r in windows.values()))
    result = {"numerical_pass": numeric, "cross_tolerance_pass": cross, "retained_under_J46_guards": retained,
              "case_profiles": cases, "period_comparisons": decisions, "pool_order": pools, "sample_days": days.tolist(),
              "verification_counts": counts, "working_scales_from_J4_J15_only": True, "historically_exposed_not_blind": True,
              "new_original_ODE_integrations": 2, "reused_original_baseline_integrations": 2,
              "optimizer_run": False, "biological_calibration": False, "production_promoted": False}
    report.mkdir(parents=True)
    write(report/"comparison.json", result)
    write_csv(report/"all55_window_metrics.csv", ["profile", "window", "pool", "source_alias", "baseline_RMSE_mM", "joint_RMSE_mM", "delta_RMSE_mM", "working_guard_failed"], rows)
    write_csv(report/"all55_samples.csv", ["profile", "pool", "day", "nominal_mM", "baseline_mM", "joint_mM"], samples)
    write(report/"verification.json", {"archive_manifest_sha256": sha(out/"manifest.json"), "verified": True,
          "rows": len(rows), "sample_rows": len(samples), "checks": counts, "numerical_pass": numeric})
    seal(report)
    check_seal(report)
    return {"numerical_pass": numeric, "retained_under_J46_guards": retained, "rows": len(rows), "checks": counts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compare-out", type=Path)
    args = parser.parse_args()
    with threadpool_limits(1):
        result = compare(args.out.resolve(), args.compare_out.resolve()) if args.compare_out else run(args.out.resolve())
    print(result)
