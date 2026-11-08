"""Reconstruct saved rates/budgets and sample live native-law preservation."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rbc_distinct_volume_transport import equadiff_distinct_volume, phase_matrix
from rbc_glut_only_transport import equadiff_glut_only
from run_glut_only_free_replay import case_options, close, observations, sha


def verify(out):
    count = 0
    def require(value, message):
        nonlocal count
        count += 1
        if not value:
            raise ValueError(message)
    context = json.loads((out / "execution_design.json").read_text())
    design, candidate = context["design"], context["candidate"]
    for name, expected in context["input_sha256"].items():
        require(sha(ROOT / name) == expected, "protected input changed: "+name)
    for name, expected in json.loads((out / "manifest.json").read_text())["output_sha256"].items():
        require(sha(out / name) == expected, "replay output changed: "+name)
    initial = np.array(context["initial_state"])
    params = json.loads((ROOT / design["initial_context"] / "frozen_parameters.json").read_text())
    names, reactions, matrix, volumes, _ = phase_matrix(design["hematocrit"], params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    t_source, obs = observations()
    require(all(initial[names.index(p)] == values[0] for p, values in obs.items()), "exact55 J1 source mismatch")
    summary = json.loads((out / "summary.json").read_text())
    ends = sorted({r["end_day"] for r in summary["results"]})
    require(ends == design["horizons_end_day"][:len(ends)], "horizons are not a gated prefix")
    require(len(summary["results"]) == len(ends)*len(design["cases"])*len(design["numerical_profiles"]), "missing case/profile results")
    all_numeric, convergence = [], []
    for end in ends:
        for case in design["cases"]:
            pair = []
            for profile in design["numerical_profiles"]:
                folder = out / f"J1_J{int(end)}" / f"{case}_{profile}"
                r = json.loads((folder / "result.json").read_text())
                with np.load(folder / "replay.npz") as a:
                    require(np.array_equal(a["initial"], initial) and np.array_equal(a["accepted_states"][:, 0], initial), "initial state changed")
                    require(a["accepted_time"][0] == 1 and a["accepted_time"][-1] == end, "truncated free replay")
                    require(np.array_equal(a["matrix"], matrix) and np.array_equal(a["pool_volumes"], volumes), "changed geometry")
                    require(np.all(a["states"][-1] == initial[-1]), "pH reference changed")
                    minimum = min(float(a["states"][:113].min()), float(a["accepted_states"][:113].min()))
                    restored = {}
                    for order in design["quadrature_orders"]:
                        nodes, weights, intervals = (a[f"q{order}_"+k] for k in ("nodes", "weights", "intervals"))
                        points = a[f"q{order}_states"]
                        require(np.all(np.isfinite(points)), "nonfinite stored quadrature state")
                        minimum = min(minimum, float(points[:113].min()))
                        for kind in ("raw", "executed"):
                            rates = a[f"q{order}_{kind}_rates"]
                            require(np.all(np.isfinite(rates)) and rates.shape[1] == len(nodes), "nonfinite or misaligned quadrature rates")
                            total = np.vstack([np.bincount(intervals, weights=row*weights, minlength=len(a["boundaries"])-1) for row in rates])
                            require(bool(close(total, a[f"{kind}{order}"], design, "quadrature").all()), "weighted integral reconstruction failed")
                            restored[order, kind] = total
                    require(minimum == r["minimum_checked_mM"], "minimum record does not match saved states")
                    source_indices = np.searchsorted(a["time"], a["boundaries"])
                    require(np.array_equal(a["time"][source_indices], a["boundaries"]), "daily audit boundaries missing")
                    increments = np.diff(a["states"][:113, source_indices], axis=1)
                    tests = [close(increments, matrix@restored[8, "executed"], design, "quadrature"),
                             close(restored[4, "raw"], restored[8, "raw"], design, "quadrature"),
                             close(restored[4, "executed"], restored[8, "executed"], design, "quadrature")]
                    numerical = bool(all(t.all() for t in tests) and minimum >= design["negative_tolerance_mM"]
                                     and r["executed_closure_max"] <= design["closure_atol_mM_per_day"]
                                     and r["raw_closure_max"] <= design["closure_atol_mM_per_day"])
                    require(numerical == r["numerical_pass"], "numerical acceptance flag changed")
                    all_numeric.append(numerical)
                    for pool in design["guard_pools"]:
                        i = names.index(pool)
                        require(float(a["states"][i, -1]) == r["endpoint"][pool], "endpoint mismatch")
                        mask = (t_source > 1) & (t_source <= end)
                        indices = np.searchsorted(a["time"], t_source[mask])
                        rmse = float(np.sqrt(np.mean((a["states"][i, indices]-obs[pool][mask])**2)))
                        require(rmse == r["source_fit_metrics"][pool]["nominal_RMSE_mM"], "source-sample RMSE mismatch")
                        totals = matrix[i]*a["executed8"].sum(axis=1)
                        for reaction, value in r["executed_pool_contributions_mM"][pool].items():
                            require(float(totals[reactions.index(reaction)]) == value, "pool attribution mismatch")
                    options = case_options(case, candidate, context["seed_kinetics"], design, params)
                    q = a["q8_nodes"]
                    for index in np.unique(np.linspace(0, len(q)-1, 7).astype(int)):
                        point = a["q8_states"][:, index]
                        audit = {}
                        d = equadiff_glut_only(q[index], point, numerical_audit=audit, **options)
                        raw, effective = [np.array([audit[k][r] for r in reactions]) for k in ("raw_fluxes", "effective_fluxes")]
                        require(np.array_equal(raw, a["q8_raw_rates"][:, index]), "sampled live raw flux differs")
                        require(np.array_equal(effective, a["q8_executed_rates"][:, index]), "sampled live executed flux differs")
                        require(np.allclose(d[:113], matrix@effective, rtol=1e-12, atol=1e-12), "live executed RHS closure failed")
                        native = {}
                        equadiff_distinct_volume(q[index], point, mode="phase_native", hematocrit=design["hematocrit"],
                            custom_params=params, numerical_audit=native, ph_policy="clamped_diagnostic",
                            positivity_policy="reaction_consistent", curve_fit_strength=0,
                            reaction_availability_threshold=design["availability_threshold_mM"])
                        require(all(audit["raw_fluxes"][r] == native["raw_fluxes"][r] for r in reactions if r != "VEGLC"),
                                "another reaction law changed at sampled state")
                    pair.append((a["states"][:113].copy(), a["raw8"].copy(), a["executed8"].copy()))
            comparisons = [close(pair[0][j], pair[1][j], design, "comparison") for j in range(3)]
            convergence.append(bool(all(x.all() for x in comparisons)))
            recorded = next(c for c in summary["convergence"] if c["case"] == case and c["end_day"] == end)
            require(convergence[-1] == recorded["passed"], "convergence record mismatch")
    numerical = all(all_numeric) and all(convergence)
    require(numerical == summary["all_numerical_pass"], "summary gate mismatch")
    if len(ends) < len(design["horizons_end_day"]):
        require(not numerical, "stopped extension without a failed numerical gate")
    require(summary["production_promoted"] is False and summary["optimization_run"] is False, "unexpected fitting/promotion")
    return {"verified": True, "checks": count, "replays": summary["replays_completed"], "last_end_day": ends[-1],
            "all_numerical_pass": numerical, "live_RHS_sampling": "seven_quadrature_states_per_replay_not_all_nodes_reexecuted",
            "full_physiological_validation": False, "production_promoted": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(verify(args.archive.resolve()), indent=2))
