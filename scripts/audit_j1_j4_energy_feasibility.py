"""Directional fixed-flux feasibility of early adenylate recovery."""

import argparse
import csv
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from threadpoolctl import threadpool_limits

from run_vsam_pgk_screen import ROOT, ADENYLATES, check_seal, read, require, seal, sha, verify_inputs, verify_manifest, write, write_csv
from run_glut_only_free_replay import close

REPLAY = ROOT/"output/vsam_pgk_j46_2026_11_04"
COMPARISON = ROOT/"output/vsam_pgk_j46_comparison_2026_11_04"
JBC = ROOT/"output/jbc_supplements_ingestion_2026_10_06"
PROTOCOL = ROOT/"tasks/fla_j1_j4_energy_protocol_2026_11_04.md"
REACTIONS = ("VPGK", "VNDPK", "VPRPPASe")
SIGNS = np.array([1., -1., -1.])
SCENARIOS = {
    "fixed": (False, False, False),
    "PGK_raw_envelope": (True, False, False),
    "demand_reduction": (False, True, True),
    "combined_raw_envelope": (True, True, True),
    "combined_no_PGK_raw_ceiling": (True, True, True),
}
TOL = 1e-8


def solve(c, a, b, bounds):
    result = linprog(c, A_ub=a, b_ub=b, bounds=bounds, method="highs",
                     options={"primal_feasibility_tolerance": 1e-9, "dual_feasibility_tolerance": 1e-9})
    require(result.success, f"unresolved LP: {result.message}")
    x, dual = result.x, result.ineqlin.marginals
    lower, upper = result.lower.marginals, result.upper.marginals
    limit = np.array([u if u is not None else np.inf for _, u in bounds])
    finite = np.isfinite(limit)
    bound = float(b@dual + limit[finite]@upper[finite])
    require(np.min(x) >= -TOL and np.all(x <= limit+TOL) and np.all(a@x <= b+TOL), "invalid primal witness")
    require(np.all(dual <= TOL) and np.all(lower >= -TOL) and np.all(upper <= TOL)
            and np.all(np.abs(upper[~finite]) <= TOL), "invalid dual sign")
    require(np.max(np.abs(c-a.T@dual-lower-upper)) <= TOL and abs(result.fun-bound) <= TOL, "invalid dual certificate")
    return x, {"objective": float(result.fun), "dual_objective": bound,
               "primal_dual_gap": float(abs(result.fun-bound))}


def screen(matrix, states, names, reactions, upper, observed, scales, design):
    aden = [names.index(p) for p in ADENYLATES]
    cols = [reactions.index(r) for r in REACTIONS]
    effect = matrix[:, cols]*SIGNS
    n = len(names)
    daily = np.kron(np.tril(np.ones((3, 3))), effect).reshape(3, n, 9)
    end = daily[-1]
    base = states[:, -1]
    h = end[aden[0]]+.5*end[aden[1]]
    h0 = float(base[aden[0]]+.5*base[aden[1]])
    demand = np.array([observed[p] for p in ADENYLATES])
    band = np.array([scales[p] for p in ADENYLATES])
    r = base[aden]-demand
    a_stock, b_stock = -daily.reshape(-1, 9), states[:, 1:].T.ravel()
    protected = [p for p in observed if p not in (*ADENYLATES, "B13PG", "P2G")]
    ix = [names.index(p) for p in protected]
    delta = base[ix]-np.array([observed[p] for p in protected])
    margins = np.array([scales[p] for p in protected])
    allowance = np.sqrt(delta**2 + design["working_MSE_allowance_fraction"]*(margins**2+delta**2))
    a_guard = np.vstack((a_stock, end[ix], -end[ix]))
    b_guard = np.r_[b_stock, allowance-delta, allowance+delta]
    a_fit = np.vstack((np.column_stack((a_guard, np.zeros(len(b_guard)))),
                       np.column_stack((end[aden], -band)), np.column_stack((-end[aden], -band))))
    b_fit = np.r_[b_guard, -r, r]
    output = {}
    for label, active in SCENARIOS.items():
        limits = np.where(active, upper, 0.)
        if label == "combined_no_PGK_raw_ceiling":
            limits[:, 0] = np.inf
        bounds = [(0., float(v) if np.isfinite(v) else None) for v in limits.ravel()]
        stock_x, stock_cert = solve(-h, a_stock, b_stock, bounds)
        guard_x, guard_cert = solve(-h, a_guard, b_guard, bounds)
        fit_x, fit_cert = solve(np.r_[np.zeros(9), 1.], a_fit, b_fit, bounds+[(0., None)])
        def witness(x):
            endpoints = states[:, 1:].T + daily@x
            return {"daily_directional_deviations_mM": x.reshape(3, 3).tolist(),
                    "minimum_endpoint_stock_mM": float(endpoints.min()),
                    "J4_adenylates_mM": endpoints[-1, aden].tolist(),
                    "J4_H_mM": float(endpoints[-1, aden[0]]+.5*endpoints[-1, aden[1]])}
        output[label] = {"maximum_H_stock_only": {**witness(stock_x), **stock_cert},
                         "maximum_H_guarded": {**witness(guard_x), **guard_cert},
                         "minimum_joint_band_multiplier": float(fit_x[-1]),
                         "best_joint_guarded": {**witness(fit_x[:-1]), **fit_cert},
                         "fits_unit_working_bands": bool(fit_x[-1] <= 1+TOL)}
    adp, prpp, b13pg = names.index("ADP"), names.index("PRPP"), names.index("B13PG")
    require(np.array_equal(effect[adp], [-1, -1, 0]) and np.array_equal(effect[prpp], [0, 0, -1])
            and np.array_equal(effect[b13pg], [-1, 0, 0]) and np.array_equal(h.reshape(3, 3)[0], [.5, .5, 1.]), "certificate stoichiometry changed")
    adp_bound = float(base[adp])
    h_bound = float(h0+.5*base[adp]+base[prpp])
    multiplier = float(max(0., (observed["ADP"]-adp_bound)/scales["ADP"]))
    for result in output.values():
        require(result["maximum_H_stock_only"]["J4_H_mM"] <= h_bound+TOL and
                result["minimum_joint_band_multiplier"] >= multiplier-TOL, "analytic certificate contradicted")
    return output, {"J4_ADP_upper_mM": adp_bound, "ADP_band_multiplier_lower_bound": multiplier,
                    "J4_H_upper_mM": h_bound, "PGK_increase_upper_from_B13PG_mM": float(base[b13pg]),
                    "PRPPASe_reduction_upper_from_PRPP_mM": float(base[prpp]),
                    "J4_ATP_plus_ADP_upper_even_if_PGK_NDPK_change_sign_mM": float(base[aden[0]]+base[adp]+base[prpp]),
                    "guarded_canonical_nonadenylates": len(protected)}


def audit_profile(path, obs, f):
    with np.load(path) as a:
        names, reactions = a["pool_names"].tolist(), a["reactions"].tolist()
        m = a["matrix"]
        t = a["time"]
        ix = np.searchsorted(t, [1, 2, 3, 4])
        require(np.array_equal(t[ix], [1, 2, 3, 4]), "daily boundaries missing")
        x = a["states"][:len(names), ix]
        initial = a["accepted_states"][:, 0]
        require(np.array_equal(initial, f["initial"]) and np.array_equal(a["initial"], initial) and
                all(initial[names.index(p)] == v[0] for p, v in obs["values"].items()), "source or latent J1 changed")
        dense_roundoff = float(np.max(np.abs(x[:, 0]-initial[:len(names)])))
        require(dense_roundoff <= 1e-12, "dense J1 disagrees with accepted initialization")
        x[:, 0] = initial[:len(names)]
        require(x.min() >= 0, "archived endpoint stock negative")
        daily = {}
        for order in (4, 8):
            mask = a[f"q{order}_intervals"] < 3
            cells, w = a[f"q{order}_intervals"][mask], a[f"q{order}_weights"][mask]
            for kind in ("raw", "executed"):
                rate = a[f"q{order}_{kind}_rates"][:, mask]
                z = np.array([np.bincount(cells, weights=v*w, minlength=3) for v in rate])
                require(close(z, a[f"{kind}{order}"][:, :3], f["numeric"], "quadrature").all(), "archive extent reconstruction mismatch")
                daily[order, kind] = z
        z, raw = daily[8, "executed"], daily[8, "raw"]
        closure = np.diff(x)-m@z
        require(close(np.diff(x), m@z, f["numeric"], "quadrature").all() and
                all(close(daily[4,k], daily[8,k], f["numeric"], "quadrature").all() for k in ("raw", "executed")), "balance or cross-quadrature failure")
        # The loop above leaves the order-8 node mask, weights and interval indices.
        nodes = a["q8_states"][:, mask]
        r8, e8 = a["q8_raw_rates"][:, mask], a["q8_executed_rates"][:, mask]
        pgk, ndpk, prpp = [reactions.index(r) for r in REACTIONS]
        substrates = [names.index(p) for p in ("B13PG", "ADP")]
        require(set(np.flatnonzero(m[:, pgk] < 0)) == set(substrates) and np.all(r8[pgk] >= 0), "unexpected PGK consuming pools or direction")
        availability = np.clip(nodes[substrates]/f["numeric"]["availability_threshold_mM"], 0, 1)
        factor = availability.min(axis=0)
        require(np.allclose(r8[pgk]*factor, e8[pgk], rtol=1e-12, atol=1e-12), "PGK limiter reconstruction changed")
        tied = np.abs(availability-factor) <= 1e-12
        lost = .5*(r8[pgk]-e8[pgk])*w
        attribution = (tied/tied.sum(axis=0))@lost
        bounds = np.column_stack((np.maximum(raw[pgk]-z[pgk], 0.),
                    *(np.bincount(cells, weights=np.maximum(e8[i], 0.)*w, minlength=3) for i in (ndpk, prpp))))
        require(np.all(e8[prpp] >= 0) and np.all(raw[pgk]-z[pgk] >= -TOL), "unexpected forward extent")
        days = obs["time"]
        observed = {p: v[days.index(4)] for p, v in obs["values"].items()}
        d = f["design"]
        scales = {p: float(d["absolute_scale_fraction"]*np.median([v[days.index(j)] for j in d["sample_days"]])+
                           d["relative_scale_fraction"]*observed[p]) for p, v in obs["values"].items()}
        require(min(scales.values()) > 0 and len(observed) == 55, "source scales incomplete")
        scenarios, certificate = screen(m, x, names, reactions, bounds, observed, scales, d)
        ai = [names.index(p) for p in ADENYLATES]
        h_row = m[ai[0]]+.5*m[ai[1]]
        a_row = m[ai].sum(axis=0)
        require(h_row[reactions.index("VAK")] == a_row[reactions.index("VAK")] == 0, "VAK balance changed")
        source = np.array([[obs["values"][p][days.index(j)] for j in (1, 4)] for p in ADENYLATES])
        h_obs = source[0]+.5*source[1]
        h_ode = x[ai[0]]+.5*x[ai[1]]
        rows = [[r, j+1, j+2, raw[i,j], z[i,j], h_row[i]*z[i,j], a_row[i]*z[i,j]]
                for i, r in enumerate(reactions) for j in range(3)]
        return {"scenarios": scenarios, "analytic_bounds": certificate,
                "H_source_J1_J4_mM": h_obs.tolist(), "H_ODE_J1_to_J4_mM": h_ode.tolist(),
                "A_source_J1_J4_mM": source.sum(axis=0).tolist(), "A_ODE_J1_to_J4_mM": x[ai].sum(axis=0).tolist(),
                "H_deficit_J4_mM": float(h_obs[-1]-h_ode[-1]),
                "adenylates_source_J4_mM": source[:, -1].tolist(), "adenylates_ODE_J4_mM": x[ai, -1].tolist(),
                "PGK_H_loss_by_limiting_pool_mM": dict(zip(("B13PG", "ADP"), attribution.tolist())),
                "PGK_H_loss_daily_mM": np.bincount(cells, weights=lost, minlength=3).tolist(),
                "NDPK_reverse_extent_mM": float(np.minimum(e8[ndpk], 0.)@w),
                "dense_J1_roundoff_max_mM": dense_roundoff,
                "max_daily_closure_residual_mM": float(np.max(np.abs(closure))),
                "daily_balance_checks": int(closure.size), "quadrature_checks": int(z.size*2),
                "stock_bounds_are_model_conditional": True, "working_bands_are_not_assay_SD": True}, rows


def yurkovich():
    receipt = read(JBC/"final_verification.json")
    require(receipt["all_cells_and_keys_match_original"], "JBC source not verified")
    relevant = {"observations_long.csv", "channel_inventory.csv", "source_conflicts.json",
                "source_files/jbc.M117.804914-1.xlsx", "source_files/jbc.M117.804914-2.pdf"}
    paths = [JBC/"final_verification.json"]
    for name, digest in receipt["output_sha256"].items():
        if name.replace("\\", "/") in relevant:
            require(sha(JBC/name) == digest, f"JBC source changed: {name}")
            paths.append(JBC/name)
    require(len(paths) == 6, "incomplete JBC provenance")
    channels = {"assay!C": "ATP", "endo!G": "ADP", "endo!H": "AMP"}
    with (JBC/"observations_long.csv").open(newline="", encoding="utf-8") as stream:
        rows = [r for r in csv.DictReader(stream) if r["temperature_C"] == "4" and r["channel_id"] in channels]
    trends = []
    for channel, name in channels.items():
        for block in ("1", "2", "3"):
            group = [r for r in rows if r["channel_id"] == channel and r["replicate_block_index"] == block]
            require(len(group) == 8 and len({r["storage_day_from_documented_origin"] for r in group}) == 8 and
                    all(r["source_unit"] == "mM" and r["training_enabled"] == "False" for r in group), "unexpected JBC sample keys or units")
            times = {float(r["storage_day_from_documented_origin"]): r for r in group}
            a, b = times[1.], times[4.]
            y0, y1 = float(a["value"]), float(b["value"])
            trends.append({"channel": channel, "label": name, "sheet_block": block, "J1_mM": y0, "J4_mM": y1,
                           "delta_mM": y1-y0, "original_cells": [a["source_cell"], b["source_cell"]]})
    require(len(rows) == 72, "unexpected JBC4C row count")
    return {"source_rows_checked": len(rows), "temperature_C": 4, "trends": trends, "ATP_pool_identity_confirmed": False,
            "cross_sheet_pairing_used": False, "energy_charge_computed": False, "used_in_LP": False}, paths


def compute():
    f = verify_inputs(REPLAY)
    verify_manifest(REPLAY)
    check_seal(COMPARISON)
    require(read(COMPARISON/"verification.json")["archive_manifest_sha256"] == sha(REPLAY/"manifest.json"), "replay receipt mismatch")
    obs = read(REPLAY/"observations.json")
    jbc, source_paths = yurkovich()
    profiles, ledger = {}, []
    for profile in f["design"]["profiles"]:
        profiles[profile], rows = audit_profile(REPLAY/"J1_J46"/("glut_real_candidate_"+profile)/"replay.npz", obs, f)
        ledger.extend([profile, *row] for row in rows)
    candidates = [key for key in SCENARIOS if key != "fixed" and key != "combined_no_PGK_raw_ceiling" and
                  all(p["scenarios"][key]["fits_unit_working_bands"] for p in profiles.values())]
    source_paths += [Path(__file__), PROTOCOL, ROOT/"qa/test_j1_j4_energy_feasibility.py",
                     REPLAY/"manifest.json", REPLAY/"source_seal.json", COMPARISON/"files_seal.json"]
    return {"profiles": profiles, "Yurkovich_4C": jbc, "admitted_flux_groups": candidates,
            "kinetic_candidate_selected": False, "new_ODE_integrations": 0,
            "input_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths}}, ledger


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--verify-receipt", type=Path)
    a = p.parse_args()
    if a.verify_receipt:
        require(not a.verify_receipt.exists() and not a.verify_receipt.resolve().is_relative_to(a.out.resolve()), "fresh external receipt required")
        check_seal(a.out)
    else:
        require(not a.out.exists(), "fresh audit directory required")
    with threadpool_limits(1):
        report, ledger = compute()
    if a.verify_receipt:
        require(report == read(a.out/"summary.json"), "recomputed audit differs")
        with (a.out/"daily_flux_ledger.csv").open(newline="", encoding="utf-8") as stream:
            rows = csv.reader(stream)
            next(rows)
            require(list(rows) == [[str(v) for v in row] for row in ledger], "recomputed ledger differs")
        a.verify_receipt.parent.mkdir(parents=True, exist_ok=True)
        write(a.verify_receipt, {"verified": True, "profile_count": len(report["profiles"]),
              "daily_flux_rows": len(ledger),
              "Yurkovich_source_rows_checked": report["Yurkovich_4C"]["source_rows_checked"],
              "admitted_flux_groups": report["admitted_flux_groups"], "archive_seal_sha256": sha(a.out/"files_seal.json")})
    else:
        a.out.mkdir(parents=True)
        write(a.out/"summary.json", report)
        write_csv(a.out/"daily_flux_ledger.csv", ["profile", "reaction", "from_day", "to_day", "raw_extent", "executed_extent",
                                                "executed_H_contribution_mM", "executed_total_adenylate_contribution_mM"], ledger)
        seal(a.out)
    print({"admitted_flux_groups": report["admitted_flux_groups"], "new_ODE_integrations": 0,
           "Yurkovich_rows": report["Yurkovich_4C"]["source_rows_checked"]})
