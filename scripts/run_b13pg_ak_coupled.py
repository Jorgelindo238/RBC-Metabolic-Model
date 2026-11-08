"""Fixed GAPDH supply / AK turnover factorial from the sealed half-step."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_vsam_pgk_screen import (ROOT, ADENYLATES, check_seal, contrast, guard, read, require,
                                 score, seal, sha, verify_inputs, verify_manifest, write, write_csv)
from fla_adenylate_sensitivity import resolve_parameters
from rbc_stoichiometry import REACTION_PARAMS
from run_broad_protected_joint import audit
from run_glut_only_free_replay import close

PARENT = ROOT/"output/vsam_pgk_j46_2026_11_04"
RECEIPT = ROOT/"output/b13pg_ak_source_2026_11_04/observation_identity.json"
PROTOCOL = ROOT/"tasks/fla_b13pg_ak_coupled_protocol_2026_11_04.md"
EARLY = ROOT/"output/j1_j4_energy_feasibility_2026_11_04"
LABELS = ("baseline", "GAPDH_up", "AK_down", "coupled")
FACTORS = ((1., 1.), (1.5, 1.), (1., .5), (1.5, .5))
GROUPS = (("vmax_VGAPDH",), ("vmax_VAK", "vmax_VAK_rev"))
ALIASES = ("B13PG", "P2G")


def changed_parameters(baseline, capacities, factors):
    result = dict(baseline)
    for group, factor in zip(GROUPS, factors):
        if factor != 1.:
            result.update({p: capacities[p]*factor for p in group})
    return result


def prepare(out):
    require(not out.exists(), "fresh successor required")
    parent = verify_inputs(PARENT)
    verify_manifest(PARENT)
    check_seal(EARLY)
    source = read(RECEIPT)
    require(source["matching_numeric_cells"] == 770 and source["exact_duplicate_pairs"] == [["B13PG", "B23PG"], ["P2G", "P3G"]]
            and not source["adenylate_free_total_confirmed"] and sha(ROOT/source["source"]) == source["source_sha256"], "source contract not verified")
    obs = read(PARENT/"observations.json")
    baseline = parent["cases"]["joint_half"]["parameters"]
    names = tuple(p for g in GROUPS for p in g)
    resolved = resolve_parameters(baseline, ROOT/"src/equadiff_brodbar.py", names)
    capacities = {p: v["value"] for p, v in resolved.items()}
    for p, r in zip(names, ("VGAPDH", "VAK", "VAK")):
        require({k for k, v in REACTION_PARAMS.items() if p in v} == {r}, "shared parameter outside declared mechanism")
    cases = {label: {"label": label, "factors": factors, "selected_log_factors": np.log(factors).tolist(),
                     "parameters": changed_parameters(baseline, capacities, factors), "glucose_kinetics": parent["kinetics"]}
             for label, factors in zip(LABELS, FACTORS)}
    inputs = [Path(__file__), PROTOCOL, RECEIPT, ROOT/"scripts/audit_b13pg_observation_identity.py",
              ROOT/"qa/test_b13pg_ak_coupled.py", PARENT/"manifest.json", PARENT/"execution_design.json",
              PARENT/"observations.json", EARLY/"files_seal.json", ROOT/source["source"]]
    f = {k: parent[k] for k in ("design", "initial", "kinetics", "parent_design", "guards", "numeric")}
    f.update(cases=cases, observation_identity=source, capacities=capacities,
             input_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in [*inputs, *(ROOT/p for p in parent["input_sha256"])]})
    out.mkdir(parents=True)
    write(out/"execution_design.json", f)
    write(out/"observations.json", obs)
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return f


def run_case(out, f, label):
    with threadpool_limits(1):
        return audit(out, f, f["cases"][label], 4.)


def run(out):
    f = prepare(out)
    print("Frozen factorial: six original free ODE runs plus fast-parity checks", flush=True)
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(run_case, out, f, label) for label in LABELS[1:]]
        audits = [job.result() for job in jobs]
    verify_inputs(out)
    write(out/"run_summary.json", {"audits": audits, "new_original_replays": 6, "new_fast_parity_replays": 3,
                                    "optimizer_run": False, "source_and_initialization_changed": False})
    write(out/"manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return {"original_pairs": len(audits), "numerical_pass": all(a["numerical_pass"] for a in audits)}


def replay_data(path, f, pools, counts):
    with np.load(path) as a:
        names, reactions, matrix = a["pool_names"].tolist(), a["reactions"].tolist(), a["matrix"]
        end = np.searchsorted(a["time"], [1, 2, 3, 4])
        require(np.array_equal(a["time"][end], [1, 2, 3, 4]) and
                np.array_equal(a["accepted_states"][:, 0], f["initial"]), "J1 or daily supports changed")
        state = a["states"][:len(names), end]
        state[:, 0] = f["initial"][:len(names)]
        integrals = {}
        for order in (4, 8):
            mask = a[f"q{order}_intervals"] < 3
            cells, weights = a[f"q{order}_intervals"][mask], a[f"q{order}_weights"][mask]
            for kind in ("raw", "executed"):
                rates = a[f"q{order}_{kind}_rates"][:, mask]
                z = np.array([np.bincount(cells, weights=v*weights, minlength=3) for v in rates])
                require(close(z, a[f"{kind}{order}"][:, :3], f["numeric"], "quadrature").all(), "archive quadrature mismatch")
                integrals[order, kind] = z
        z = integrals[8, "executed"]
        balance = close(np.diff(state), matrix@z, f["numeric"], "quadrature")
        checks = [close(integrals[4, k], integrals[8, k], f["numeric"], "quadrature") for k in ("raw", "executed")]
        require(balance.all() and all(v.all() for v in checks), "budget or order convergence failed")
        counts["daily_balances"] += balance.size
        counts["quadrature"] += sum(v.size for v in checks)
        prediction = state[[names.index(p) for p in pools], -1]
        m = {p: matrix[names.index(p)] for p in (*ADENYLATES, "B13PG", "NADH")}
        m.update(H=m["ATP"]+.5*m["ADP"], A=sum(m[p] for p in ADENYLATES))
        budgets = {}
        for label, js in (("J1_J2", slice(0, 1)), ("J2_J4", slice(1, 3)), ("J1_J4", slice(0, 3))):
            raw, executed = (integrals[8, k][:, js].sum(axis=1) for k in ("raw", "executed"))
            budgets[label] = {"raw_integrals": dict(zip(reactions, raw.tolist())), "executed_integrals": dict(zip(reactions, executed.tolist())),
                              "executed_pool_terms_mM": {p: dict(zip(reactions, (row*executed).tolist())) for p, row in m.items()}}
        return {"J4_prediction_mM": prediction.tolist(), "budgets": budgets,
                "J4_latent_context_mM": {p: float(state[names.index(p), -1]) for p in ("NAD", "NADH", "GA3P", "PRPP", "GTP")}}


def mechanism(candidate, baseline, pools):
    a, b = candidate["budgets"], baseline["budgets"]
    diff = {r: a["J2_J4"]["executed_integrals"][r]-b["J2_J4"]["executed_integrals"][r] for r in ("VGAPDH", "VPGK")}
    ak = a["J1_J4"]["executed_integrals"]["VAK"]-b["J1_J4"]["executed_integrals"]["VAK"]
    adp = candidate["J4_prediction_mM"][pools.index("ADP")]-baseline["J4_prediction_mM"][pools.index("ADP")]
    return {"J2_J4_executed_deltas_mM": diff, "J1_J4_VAK_delta_mM": ak, "J4_ADP_delta_mM": adp,
            "pass": bool(min(diff.values()) > 1e-6 and ak < -1e-6 and adp > 1e-6)}


def compare(out, dest):
    require(not dest.exists() and not dest.is_relative_to(out), "fresh comparison outside sealed run required")
    verify_manifest(out)
    f, obs = verify_inputs(out), read(out/"observations.json")
    design = f["design"]
    profiles = design["profiles"]
    pools, days = list(obs["values"]), obs["time"]
    canonical = [p for p in pools if p not in ALIASES]
    ix = [pools.index(p) for p in canonical]
    target = np.array([obs["values"][p][days.index(4)] for p in pools])
    bands = design["absolute_scale_fraction"]*np.median([[v[days.index(t)] for t in design["sample_days"]] for v in obs["values"].values()], axis=1) + design["relative_scale_fraction"]*target
    require((bands > 0).all() and len(pools) == 55, "invalid working bands")
    counts = {"daily_balances": 0, "quadrature": 0}
    cases, csv_rows = {}, []
    audits = {r["label"]: r for r in read(out/"run_summary.json")["audits"]}
    for label in LABELS:
        folder, horizon = (PARENT, 46) if label == "baseline" else (out/"audits"/(label+"_J4"), 4)
        if label != "baseline":
            check_seal(folder)
        cases[label] = {"numerical_pass": True if label == "baseline" else audits[label]["numerical_pass"], "profiles": {}}
        for profile in profiles:
            data = replay_data(folder/f"J1_J{horizon}"/f"glut_real_candidate_{profile}"/"replay.npz", f, pools, counts)
            x = np.array(data["J4_prediction_mM"])
            data["metrics"] = score(x[ix, None], target[ix, None], bands[ix, None], canonical)
            cases[label]["profiles"][profile] = data
    decisions = {}
    for profile in profiles:
        ref = cases["baseline"]["profiles"][profile]
        for label in LABELS:
            r = cases[label]["profiles"][profile]
            r["guard"] = guard(r["metrics"], ref["metrics"], canonical, [4], design)
            r["mechanism"] = mechanism(r, ref, pools)
            for i, p in enumerate(pools):
                csv_rows.append([label, profile, p, p in ALIASES, target[i], r["J4_prediction_mM"][i],
                                 ref["J4_prediction_mM"][i], p in r["guard"]["all55_failures"]])
        best = min((label for label in LABELS[:-1] if label == "baseline" or
                    (cases[label]["numerical_pass"] and cases[label]["profiles"][profile]["guard"]["pass"])),
                   key=lambda label: cases[label]["profiles"][profile]["metrics"]["adenylate_log_mean"])
        errors = [cases[label]["profiles"][profile]["metrics"]["adenylate_log_mean"] for label in LABELS]
        joint = cases["coupled"]["profiles"][profile]
        increment = cases[best]["profiles"][profile]["metrics"]["adenylate_log_mean"]-errors[-1]
        decisions[profile] = {"best_admissible_control": best, "increment_over_control": increment,
                              "log_MSE_four_corner_contrast": float(contrast(*errors)),
                              "admitted": bool(cases["coupled"]["numerical_pass"] and joint["guard"]["pass"] and joint["mechanism"]["pass"]
                                               and increment >= design["minimum_increment_over_admissible_single_fraction_of_baseline"]*errors[0])}
    result = {"cases": cases, "profile_decisions": decisions, "coupled_admitted": all(v["admitted"] for v in decisions.values()),
              "pool_order": pools, "counts": counts, "J4_nominal_mM": target.tolist(), "new_original_replays": 6,
              "source_identity": f["observation_identity"], "optimizer_run": False, "production_promoted": False,
              "biological_calibration": False}
    dest.mkdir(parents=True)
    write(dest/"comparison.json", result)
    write_csv(dest/"all55_J4.csv", ["case", "profile", "pool", "source_alias", "nominal_mM", "prediction_mM", "baseline_mM", "guard_failed"], csv_rows)
    write(dest/"verification.json", {"verified": True, "pool_comparisons": len(csv_rows), "counts": counts,
                                    "archive_manifest_sha256": sha(out/"manifest.json")})
    seal(dest)
    check_seal(dest)
    return {"coupled_admitted": result["coupled_admitted"], "pool_comparisons": len(csv_rows), "counts": counts}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--compare-out", type=Path)
    a = p.parse_args()
    with threadpool_limits(1):
        result = compare(a.out.resolve(), a.compare_out.resolve()) if a.compare_out else run(a.out.resolve())
    print(result)
