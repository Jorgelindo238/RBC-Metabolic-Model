"""Recheck search traces, Vmax-only scope, and accepted-grid original balances."""

import argparse
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_agentic_vmax_pilot import (STRUCTURE, check_seal, compare_metrics, measure, panel_from_observations,
                                    parameters_for, read, require, rhs_for, sha, verify_inputs, verify_manifest, within, write)


def verify(out):
    f, obs = verify_inputs(out), read(out/"observations.json")
    verify_manifest(out)
    d, n = f["design"], f["numeric"]
    result = read(out/"validation_summary.json")
    fit = panel_from_observations(obs, d["fit_days"], d)
    reference = measure(np.array(f["reference_predictions"]["ultrastrict"])[:, :1], fit)
    checks = {"actual_attempts": 0, "fitted_score_rows": 0, "original_daily_balances": 0,
              "quadrature_reconstructions": 0, "native_rate_checkpoints": 0, "source_audit_rows": 0}
    for mode in STRUCTURE:
        folder = out/"search"/mode
        check_seal(folder)
        s = read(folder/"result.json")
        rows = [json.loads(line) for line in (folder/"trace.jsonl").read_text().splitlines()]
        require(rows == s["trace"], "progress trace differs from sealed search")
        evaluations = [r for r in rows if r["source"] == "evaluation"]
        require(len(evaluations) == s["actual_evaluations"] <= d["budget_per_network"] and
                len(rows)-len(evaluations) == s["cache_hits"] and
                len({tuple(r["log_factors"]) for r in evaluations}) == len(evaluations), "attempt budget/cache mismatch")
        checks["actual_attempts"] += len(evaluations)
        for r in evaluations:
            factors = np.exp(r["log_factors"])
            bounds = np.array([d["factor_bounds"][k] for k in d["groups"]])
            require(np.all(factors >= bounds[:, 0]-1e-12) and np.all(factors <= bounds[:, 1]+1e-12), "unregistered exploration point")
            if r["failure"] is not None:
                require(not r["feasible"], "failed trial admitted")
                continue
            m = measure(r["callback_result"]["metrics"]["prediction_mM"], fit)
            c = compare_metrics(m, reference, fit, d)
            for k in ("adenylate_loss", "other_loss", "max_guard_excess"):
                require(abs(c[k]-r[k]) < 1e-12, "fit objective not reproducible")
            require(r["feasible"] == c["guards_pass"], "fit feasibility changed")
            checks["fitted_score_rows"] += 1
        p = parameters_for(f, s["finalist"]["log_factors"])
        require(p == result["networks"][mode]["parameters"] and
                all(p[k] == v for k, v in f["parameters"].items() if not k.startswith("vmax_")), "non-Vmax mutation")
        require(all(p[k] == v for k, v in f["parameters"].items() if k.startswith("vmax_") and v == 0), "closed capacity changed")
        rhs = rhs_for(f, p, mode, "full")
        for profile in ("strict", "ultrastrict"):
            base = out/"audits"/mode/profile
            check_seal(base)
            report = read(base/"result.json")
            with np.load(base/"replay.npz") as a:
                names, time, states, matrix = a["pool_names"].tolist(), a["time"], a["states"], a["matrix"]
                require(np.array_equal(a["accepted_states"][:, 0], f["initial"]) and np.array_equal(matrix, rhs.matrix), "replay changed J1 or network")
                for order in (4, 8):
                    for kind in ("raw", "executed"):
                        z = np.array([np.bincount(a[f"q{order}_intervals"], weights=v*a[f"q{order}_weights"], minlength=14)
                                      for v in a[f"q{order}_{kind}_rates"]])
                        require(within(z, a[f"{kind}{order}"], n, "quadrature").all(), "quadrature reconstruction mismatch")
                        checks["quadrature_reconstructions"] += z.size
                inc = np.diff(states[:113, np.searchsorted(time, a["boundaries"])])
                balance = within(inc, matrix@a["executed8"], n, "quadrature")
                require(balance.all() == (report["checks"]["daily_balance"]["passed"] == balance.size), "numerical flag mismatch")
                checks["original_daily_balances"] += int(balance.sum())
                for j, (t, x) in enumerate(zip(a["live_time"], a["live_states"].T)):
                    raw, exec_, _ = rhs.rates(t, x)
                    require(np.allclose(raw, a["live_raw"][:, j], rtol=1e-12, atol=1e-12) and
                            np.allclose(exec_, a["live_executed"][:, j], rtol=1e-12, atol=1e-12), "live original-rate mismatch")
                    checks["native_rate_checkpoints"] += 1
                for label, ix in (("fit_J4", [0]), ("check_J8_J15", [1, 2, 3])):
                    panel = panel_from_observations(obs, [d["audit_days"][i] for i in ix], d)
                    x = states[np.ix_([names.index(k) for k in panel["names"]], np.searchsorted(time, panel["days"]))]
                    m = measure(x, panel)
                    ref = measure(np.array(f["reference_predictions"][profile])[:, ix], panel)
                    c = compare_metrics(m, ref, panel, d)
                    require(c["off_target_failures"] == report["periods"][label]["off_target_failures"] and
                            abs(c["adenylate_loss"]-report["periods"][label]["adenylate_loss"]) < 1e-12,
                            "original sample score or guard mismatch")
                    checks["source_audit_rows"] += len(panel["names"])
    return {"verified": True, "checks": checks, "archive_manifest_sha256": sha(out/"manifest.json"),
            "non_Vmax_parameters_frozen": True, "global_optimality": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    a = p.parse_args()
    require(not a.receipt.exists() and not a.receipt.resolve().is_relative_to(a.out.resolve()), "fresh external verification required")
    with threadpool_limits(1):
        result = verify(a.out.resolve())
    write(a.receipt, result)
    print(result)
