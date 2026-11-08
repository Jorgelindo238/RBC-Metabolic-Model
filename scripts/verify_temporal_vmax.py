"""Rebuild the dated decisions and signed budgets from original trajectories."""

import argparse
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_temporal_vmax import (check_seal, parameters_for, read, require, rhs_for, seal, sha,
                               verify_inputs, within, write, write_csv)
from report_agentic_vmax_pilot import signed_budget


def verify(out, report):
    require(not report.exists() and not report.is_relative_to(out), "fresh external receipt required")
    manifest = read(out/"manifest.json")
    actual = {path.relative_to(out).as_posix(): sha(path) for path in out.rglob("*")
              if path.is_file() and path != out/"manifest.json"}
    require(actual == manifest, "campaign manifest mismatch")
    f, obs = verify_inputs(out), read(out/"observations.json")
    d, p, n = f["design"], f["temporal"], f["numeric"]
    result = read(out/"validation_summary.json")
    check_seal(out/"fit")
    fit = read(out/"fit/result.json")
    trace = [json.loads(line) for line in (out/"fit/trace.jsonl").read_text().splitlines()]
    require(len(trace) == fit["actual_attempts"] <= fit["maximum_attempts"] and
            len({tuple(r["log_factors"]) for r in trace}) == len(trace), "attempt count/cache mismatch")
    require(trace[fit["selected"]["attempt"]-1] == fit["selected"], "selection not an actual evaluated trajectory")
    days, pools = p["fit_days"], list(obs["values"])
    measured = np.array([[obs["values"][k][obs["time"].index(t)] for t in days] for k in pools])
    early = np.column_stack(([obs["values"][k][0] for k in pools], measured))
    bands = .05*np.median(early, axis=1)[:, None]+.2*measured
    aden = [pools.index(x) for x in ("ATP", "ADP", "AMP")]
    limits = np.array([d["factor_bounds"][g] for g in d["groups"]])
    fit_ref = np.array(trace[0]["prediction_mM"])[aden]
    e0 = np.mean(np.log(fit_ref/measured[aden])**2, axis=0)
    checks = {"fit_score_rows": 0, "critical_pointwise_rows": 0, "daily_balances": 0,
              "quadrature_reconstructions": 0, "live_rate_checkpoints": 0}
    for row in trace:
        factors = np.exp(row["log_factors"])
        require(np.all(factors >= limits[:,0]-1e-12) and np.all(factors <= limits[:,1]+1e-12), "factor outside registered box")
        if not row["valid"]:
            continue
        ratios = np.mean(np.log(np.array(row["prediction_mM"])[aden]/measured[aden])**2, axis=0)/e0
        require(np.allclose(ratios, row["day_ratios"], rtol=1e-12, atol=1e-12) and abs(ratios.max()-row["objective"]) < 1e-12,
                "dated optimization objective changed")
        checks["fit_score_rows"] += 1
    vector = fit["selected"]["log_factors"]
    final = parameters_for(f, vector)
    require(all(final[k] == v for k,v in f["parameters"].items() if not k.startswith("vmax_") or v == 0), "fixed Km or closed capacity changed")
    require({k: final[k] for k in f["resolved_capacities"]} == result["selected_Vmax"], "Vmax export mismatch")
    critical, budgets = [], {}
    for profile in ("strict", "ultrastrict"):
        x = {}
        for label, parameters in (("corrected_reference", f["parameters"]), ("temporal_candidate", final)):
            folder = out/"audits"/label/profile
            check_seal(folder)
            rhs = rhs_for(f, parameters, p["network"], "full")
            stats = read(folder/"result.json")
            with np.load(folder/"replay.npz") as a:
                names, time, matrix, states = a["pool_names"].tolist(), a["time"], a["matrix"], a["states"]
                require(np.array_equal(a["accepted_states"][:,0], f["initial"]) and np.array_equal(matrix, rhs.matrix), "replay changed J1 or network")
                for order in (4, 8):
                    weights, cells = a[f"q{order}_weights"], a[f"q{order}_intervals"]
                    for kind in ("raw", "executed"):
                        integral = np.array([np.bincount(cells, weights=v*weights, minlength=14) for v in a[f"q{order}_{kind}_rates"]])
                        require(within(integral, a[f"{kind}{order}"], n, "quadrature").all(), "quadrature reconstruction failed")
                        checks["quadrature_reconstructions"] += integral.size
                inc = np.diff(states[:113, np.searchsorted(time, a["boundaries"])])
                balance = within(inc, matrix@a["executed8"], n, "quadrature")
                require(int(balance.sum()) == stats["checks"]["daily_balance"]["passed"], "daily closure flag changed")
                checks["daily_balances"] += int(balance.sum())
                for j, (t, state) in enumerate(zip(a["live_time"], a["live_states"].T)):
                    raw, executed, _ = rhs.rates(t, state)
                    require(np.allclose(raw, a["live_raw"][:,j], rtol=1e-12, atol=1e-12) and
                            np.allclose(executed, a["live_executed"][:,j], rtol=1e-12, atol=1e-12), "native projection changed")
                    checks["live_rate_checkpoints"] += 1
                ix = np.searchsorted(time, days)
                require(np.array_equal(time[ix], days), "actual observation support changed")
                x[label] = states[np.ix_([names.index(k) for k in pools], ix)]
            if profile == "ultrastrict":
                budgets[label] = signed_budget(folder/"replay.npz")
        base, candidate = (x[k] for k in ("corrected_reference", "temporal_candidate"))
        b0, bc = np.abs(base-measured), np.abs(candidate-measured)
        recorded = result["original_metrics"][profile]
        gain = 1-np.mean(np.log(candidate[aden]/measured[aden])**2, axis=0)/np.mean(np.log(base[aden]/measured[aden])**2, axis=0)
        require(np.allclose(gain, recorded["gain_by_day"], rtol=1e-12, atol=1e-12), "original dated gain changed")
        for key in p["critical_pointwise_pools"]:
            i = pools.index(key)
            for j, day in enumerate(days):
                cap = np.sqrt(b0[i,j]**2+d["working_allowance_fraction"]*(bands[i,j]**2+b0[i,j]**2)) if bands[i,j] else b0[i,j]+d["zero_band_absolute_allowance_mM"]
                slack = (bc[i,j]-cap)/max(bands[i,j]+cap, 1e-6)
                require(abs(slack-recorded["guards"][f"point:{key}:J{day}"]) < 1e-12, "pointwise guard changed")
                critical.append([profile, key, day, measured[i,j], base[i,j], candidate[i,j], cap, bool(bc[i,j] <= cap)])
                checks["critical_pointwise_rows"] += 1
    report.mkdir(parents=True)
    write(report/"verification.json", {"verified": True, "checks": checks, "attempts": len(trace),
                                        "archive_manifest_sha256": sha(out/"manifest.json"), "all_Km_frozen": True})
    write(report/"executed_ATP_H_budgets.json", budgets)
    write_csv(report/"critical_dated_guards.csv", ["profile", "pool", "day", "nominal_mM", "reference_mM", "candidate_mM", "abs_error_cap_mM", "pass"], critical)
    write_csv(report/"selected_Vmax.csv", ["parameter", "reference_Vmax", "tested_Vmax", "factor", "admitted_under_temporal_guards", "production_promoted"],
              [[k, f["parameters"][k], v, v/f["parameters"][k], result["admitted_under_temporal_guards"], False] for k,v in result["selected_Vmax"].items()])
    seal(report)
    check_seal(report)
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with threadpool_limits(1):
        print(verify(args.out.resolve(), args.report.resolve()))
