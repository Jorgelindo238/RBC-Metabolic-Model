"""Read-only signed ATP demand audit of sealed original AIRBC replays."""

import argparse
import csv
import io
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_vsam_pgk_screen import ROOT, check_seal, read, require, sha, verify_inputs, verify_manifest
from run_glut_only_free_replay import close
from audit_b13pg_observation_identity import audit as source_audit
from fla_adenylate_sensitivity import resolve_parameters
from rbc_distinct_volume_transport import phase_matrix
from rbc_stoichiometry import REACTION_PARAMS


BASE = ROOT / "output/vsam_pgk_j46_2026_11_04"
FACTORIAL = ROOT / "output/b13pg_ak_coupled_2026_11_04"
COMPARISON = ROOT / "output/b13pg_ak_coupled_comparison_2026_11_04"
DEST = ROOT / "output/agentic_atp_demand_2026_11_04"
WINDOWS = ((1, 2), (2, 4), (4, 8), (8, 15), (15, 46))
LABELS = ("half_step", "GAPDH_up", "AK_down", "coupled")
ADEN = ("ATP", "ADP", "AMP")
STOCKS = ("RIB", "R5P", "PRPP", "GDP", "GTP", "GMP", "ADESUC", "IMP", "ADO",
          "ADOMET", "SAH", "GLC", "G6P", "F6P", "F16BP", "GA3P", "B13PG",
          "B23PG", "PEP", "NAD", "NADH", "GLUCYS", "GSH", "GSSG", "OXOP")
MECHANISMS = {
    "adenylate_redistribution": ("VAK",),
    "glycolytic_payoff_transfer": ("VPGK", "VPK"),
    "glycolytic_investment_transfer": ("VHK", "VPFK"),
    "ribose_phosphate_transfer": ("VRKa",),
    "guanylate_phosphate_transfer": ("VNDPK", "VGMPK"),
    "pyrophosphoryl_transfer_to_PRPP": ("VPRPPASe",),
    "ATP_cleavage_GMP_synthesis": ("VGMPS",),
    "hydrolysis_coupled_biosynthesis": ("VGLNS", "VGLUCYS", "VGSS", "VOPLAH"),
    "adenylate_moiety_exit_to_SAM": ("VSAM",),
    "adenosine_salvage_transfer": ("VAK2",),
    "AMP_exit_no_direct_H_cost": ("VAMPD1", "VAMP_NT"),
    "AMP_entry_no_direct_H_gain": ("VAPRT", "VADSL"),
}
CLASS = {r: k for k, rs in MECHANISMS.items() for r in rs}
KINDS = ("raw", "executed")
METRICS = ("ATP", "ADP", "AMP", "H", "A")


def window_id(left, right):
    return f"J{left}_J{right}"


def directional_daily(rates, weights, cells, days):
    """Forward/reverse magnitudes of the signed NET rate, split before quadrature."""
    return np.array([
        [np.bincount(cells, weights=np.maximum(sign * rate, 0) * weights, minlength=days)
         for rate in rates]
        for sign in (1, -1)
    ])


def projected(coefficient, extent):
    """Return separate production, consumption and net by reaction."""
    fwd, rev = extent
    plus, minus = np.maximum(coefficient, 0), np.maximum(-coefficient, 0)
    production = plus * fwd + minus * rev
    consumption = minus * fwd + plus * rev
    return np.array([production, consumption, production - consumption])


def totals(terms):
    return dict(zip(("production_mM", "consumption_mM", "net_mM"), terms.sum(axis=-1).tolist()))


def pool_ledger(row, x0, x1, extent, reactions):
    terms = projected(row, extent)
    out = totals(terms)
    draw = max(float(x0 - x1), 0.)
    return dict(out, start_mM=float(x0), end_mM=float(x1), state_delta_mM=float(x1 - x0),
                net_stock_drawdown_mM=draw,
                net_drawdown_fraction_of_outflow=draw / out["consumption_mM"] if out["consumption_mM"] else None,
                net_terms_mM={r: float(v) for r, c, v in zip(reactions, row, terms[2]) if c})


def limiter_loss(column, availability, raw, executed, weights):
    """Split positive-direction suppressed extent among tied consuming pools."""
    consuming = np.flatnonzero(column < 0)
    require(consuming.size > 0, "positive-direction limiter requires substrates")
    a = availability[consuming]
    tied = np.abs(a - a.min(axis=0)) <= 1e-12
    loss = (np.maximum(raw, 0) - np.maximum(executed, 0)) * weights
    return consuming, (tied / tied.sum(axis=0)) @ loss


def inspect(path, profile, end, frozen, network):
    """Rebuild daily directional quadrature and verify it against sealed states and rates."""
    names, rs, matrix, pv, rv = network
    numeric = frozen["numeric"]
    meta = read(path.with_name("result.json"))
    require(meta["numerical_pass"] and meta["profile"] == profile and meta["end_day"] == end
            and meta["GLC_is_free_state"] and meta["native_VELAC_law_unchanged"],
            f"nonmatched replay: {path}")
    daily = {}
    with np.load(path) as a:
        require(tuple(a["pool_names"]) == names and tuple(a["reactions"]) == rs
                and all(np.array_equal(a[k], v) for k, v in (
                    ("matrix", matrix), ("pool_volumes", pv), ("reaction_volumes", rv))),
                f"phase matrix mismatch: {path}")
        days = np.arange(1, end + 1)
        ix = np.searchsorted(a["time"], days)
        require(np.array_equal(a["boundaries"], days) and np.array_equal(a["time"][ix], days)
                and np.array_equal(a["accepted_time"][[0, -1]], days[[0, -1]]),
                f"missing exact daily support: {path}")
        initial = np.array(frozen["initial"])
        x = a["states"][:len(names), ix]
        require(np.array_equal(a["initial"], initial) and np.array_equal(a["accepted_states"][:, 0], initial)
                and np.max(np.abs(x[:, 0] - initial[:len(names)])) <= 1e-12,
                f"initialization mismatch: {path}")
        x[:, 0] = initial[:len(names)]
        require(np.isfinite(x).all() and x.min() >= numeric["negative_tolerance_mM"],
                f"invalid daily states: {path}")
        for order in (4, 8):
            nodes, cells, weights, states, raw, executed = (
                a[f"q{order}_{k}"] for k in ("nodes", "intervals", "weights", "states", "raw_rates", "executed_rates")
            )
            require(np.issubdtype(cells.dtype, np.integer) and np.all((0 <= cells) & (cells < end-1))
                    and np.all((days[cells] < nodes) & (nodes < days[cells+1]))
                    and np.all(weights > 0)
                    and np.allclose(np.bincount(cells, weights=weights, minlength=end-1), 1, rtol=0, atol=1e-12),
                    f"invalid quadrature support: {path}")
            require(all(np.isfinite(v).all() for v in (states, raw, executed))
                    and states[:len(names)].min() >= numeric["negative_tolerance_mM"],
                    f"invalid quadrature states or rates: {path}")
            for kind, rates in zip(KINDS, (raw, executed)):
                d = directional_daily(rates, weights, cells, end-1)
                require(close(d[0] - d[1], a[f"{kind}{order}"], numeric, "quadrature").all(),
                        f"sealed signed extent mismatch: {path}")
                daily[order, kind] = d
        availability = np.clip(states[:len(names)] / numeric["availability_threshold_mM"], 0, 1)
        for j, col in enumerate(matrix.T):
            left, right = availability[col < 0], availability[col > 0]
            fwd = left.min(axis=0) if len(left) else 1.
            rev = right.min(axis=0) if len(right) else 1.
            require(np.allclose(raw[j] * np.where(raw[j] >= 0, fwd, rev), executed[j], rtol=1e-12, atol=1e-12),
                    f"signed limiter mismatch: {path}/{rs[j]}")
        signed = daily[8, "executed"][0] - daily[8, "executed"][1]
        actual, reconstructed = np.diff(x), matrix @ signed
        require(close(actual, reconstructed, numeric, "quadrature").all(), f"daily balance fails: {path}")
        require(all(close(daily[4, k], daily[8, k], numeric, "quadrature").all() for k in KINDS),
                f"directional order convergence fails: {path}")
        loss = {}
        for left, right in WINDOWS:
            if right > end:
                continue
            mask = (cells >= left-1) & (cells < right-1)
            loss[window_id(left, right)] = {}
            for r in ("VPGK", "VPK", "VNDPK", "VPRPPASe", "VPFK"):
                j = rs.index(r)
                ii, v = limiter_loss(matrix[:, j], availability[:, mask], raw[j, mask],
                                     executed[j, mask], weights[mask])
                loss[window_id(left, right)][r] = {names[i]: float(vv) for i, vv in zip(ii, v)}
        checks = {"daily_pool_balances": int(actual.size), "directional_order_checks": int(2 * d.size),
                  "archived_signed_extent_checks": int(4 * signed.size),
                  "node_limiter_checks": int(executed.size),
                  "max_daily_executed_pool_residual_mM": float(np.max(np.abs(actual - reconstructed)))}
    return x, {k: daily[8, k] for k in KINDS}, loss, checks


def ledgers(case, profile, x, daily, loss, network):
    names, rs, matrix, _, _ = network
    indices = {p: i for i, p in enumerate(names)}
    aden = matrix[[indices[p] for p in ADEN]]
    coeff = np.vstack((aden, aden[0] + .5*aden[1], aden.sum(axis=0)))
    require({r for r, c in zip(rs, aden.T) if np.any(c)} == CLASS.keys(), "unclassified adenylate reaction")
    stocks = np.vstack((x[[indices[p] for p in ADEN]],
                        x[indices["ATP"]] + .5*x[indices["ADP"]], x[[indices[p] for p in ADEN]].sum(axis=0)))
    results, rows = {}, []
    for left, right in WINDOWS:
        if right > x.shape[1]:
            continue
        tag = window_id(left, right)
        i, j = left - 1, right - 1
        delta = stocks[:, j] - stocks[:, i]
        window = {"days": [left, right], "positive_limiter_loss_extent_mM": loss[tag]}
        for kind in KINDS:
            extent = daily[kind][:, :, i:j].sum(axis=2)
            terms = {metric: projected(c, extent) for metric, c in zip(METRICS, coeff)}
            window[kind] = {}
            for m, start, finish, change in zip(METRICS, stocks[:, i], stocks[:, j], delta):
                t = totals(terms[m])
                balance = dict(t, start_mM=float(start), end_mM=float(finish), state_delta_mM=float(change))
                key = "closure_residual_mM" if kind == "executed" else "state_delta_minus_raw_net_mM"
                balance[key] = float(change - t["net_mM"])
                balance["production_over_consumption"] = (t["production_mM"] / t["consumption_mM"]
                                                           if t["consumption_mM"] else None)
                balance["by_mechanism"] = {k: totals(terms[m][:, [rs.index(r) for r in reactions]])
                                           for k, reactions in MECHANISMS.items()}
                window[kind][m] = balance
            for k, r in enumerate(rs):
                rows.append([case, profile, tag, kind, r, CLASS.get(r, "context_no_direct_adenylate_term"),
                             *coeff[:, k].tolist(), *extent[:, k].tolist(), float(extent[0, k]-extent[1, k]),
                             *(float(v) for m in METRICS for v in terms[m][:, k])])
            if kind == "executed":
                window["stock_ledgers"] = {p: pool_ledger(matrix[k], x[k, i], x[k, j], extent, rs)
                                           for p in STOCKS for k in (indices[p],)}
        window["executed_minus_raw_net_mM"] = {m: window["executed"][m]["net_mM"] - window["raw"][m]["net_mM"]
                                               for m in METRICS}
        results[tag] = window
    return results, rows


def matched_delta(base, alt):
    deltas = {}
    for tag, window in alt.items():
        require(tag in base, f"nonmatched comparison: {tag}")
        deltas[tag] = {}
        for kind in KINDS:
            deltas[tag][kind] = {}
            for m in METRICS:
                a, b = window[kind][m], base[tag][kind][m]
                d = {key: a[key]-b[key] for key in ("production_mM", "consumption_mM", "net_mM", "end_mM")}
                # Positive overlap is the supply increment absorbed by an increment in demand.
                p, c = d["production_mM"], d["consumption_mM"]
                d["added_production_offset_by_added_consumption_mM"] = max(0., min(p, c))
                d["added_consumption_over_added_production"] = c / p if p > 0 and c >= 0 else None
                d["net_by_mechanism_mM"] = {k: a["by_mechanism"][k]["net_mM"]-b["by_mechanism"][k]["net_mM"]
                                             for k in MECHANISMS}
                deltas[tag][kind][m] = d
    return deltas


def priority_groups(parameters, windows, rows, network):
    names, rs, matrix, _, _ = network
    specs = [
        ("ribose_investment", "primary", (("vmax_VRKa", "VRKa"),), (.5, 1.),
         "Lower the J1-J2 RIB-funded pulse; 0.5 is a deliberate pulse-timing stress start, not a promise of lower cumulative flux.",
         ("RIB", "R5P", "PRPP", "ATP", "ADP"), ("purine_PRPP_alternate",)),
        ("guanylate_transfer", "primary", (("vmax_VNDPK", "VNDPK"), ("vmax_VNDPK_rev", "VNDPK")), (.75, 1.),
         "Lower shared turnover modestly to test early net ATP-to-GTP transfer without changing the capacity ratio. Can also remove reverse recovery; guard GTP-funded VADSS.",
         ("GDP", "GTP", "GMP", "ADESUC", "IMP", "AMP", "ADP"), ()),
        ("PFK_investment", "guarded_secondary", (("vmax_VPFK", "VPFK"),), (.9, 1.),
         "Modest downward carbon-investment start only; lower demand can lower glycolytic payoff or accumulate F6P. Hold HK independently fixed.",
         ("GLC", "G6P", "F6P", "F16BP", "PEP", "ATP", "ADP"), ()),
        ("purine_PRPP_alternate", "alternate_not_joint_with_RKa_initially", (("vmax_VPRPPASe", "VPRPPASe"),), (.9, 1.),
         "Modest down-test: a whole unit of H per extent but not generic ATPase. Initial PRPP buffers early salvage; preserve PRPP-dependent purines. R5P links this to RKa.",
         ("R5P", "PRPP", "IMP", "GMP", "AMP"), ("ribose_investment",)),
    ]
    resolved = resolve_parameters(parameters, ROOT / "src/equadiff_brodbar.py",
                                  [p for s in specs for p, _ in s[2]])
    row_index = {(row[2], row[4]): row for row in rows if row[:2] == ["half_step", "ultrastrict"]
                 and row[3] == "executed"}
    groups = []
    for label, tier, keys, factors, why, guards, conflicts in specs:
        reaction = keys[0][1]
        members = []
        for p, r in keys:
            require(p.startswith("vmax_") and {k for k, v in REACTION_PARAMS.items() if p in v} == {r},
                    f"parameter support mismatch: {p}")
            v = resolved[p]
            members.append(dict(v, key=p, reaction=r, bounds=[v["value"]*f for f in factors]))
        col = matrix[:, rs.index(reaction)]
        support = {}
        for tag in windows:
            row = row_index[tag, reaction]
            support[tag] = dict(zip(("forward_extent_mM", "reverse_extent_mM", "signed_extent_mM",
                                    "ATP_production_mM", "ATP_consumption_mM", "ATP_net_mM"), row[11:17]))
            support[tag]["H_net_mM"] = row[25]
        groups.append({"id": label, "tier": tier, "direction": "down_from_half_step",
                       "coordinate": "shared_multiplier" if len(keys) > 1 else "single_multiplier",
                       "multiplier_bounds": list(factors), "suggested_multipliers": [factors[0], float(np.sqrt(factors[0])), 1.],
                       "parameters": members, "reaction_class": CLASS[reaction],
                       "stoichiometry": {p: float(v) for p, v in zip(names, col) if v},
                       "executed_ultrastrict_support": support, "rationale": why, "guard_pools": list(guards),
                       "initial_screen_excludes_groups": list(conflicts)})
    return {"schema_version": 1, "reference_case": "half_step", "bounds_are_engineering_starts_not_priors": True,
            "fixed": {"all_Km": True, "exact55_J1": True, "all_latents_and_pH_J1": True,
                      "OPLAH": parameters["vmax_VOPLAH"], "all_unlisted_parameters": True,
                      "half_step_PGK_and_SAM": True, "reaction_availability_threshold_mM": .001},
            "screen_order": ["Single-coordinate starts first with unmodified half-step as a control.",
                             "Only combine independently guarded coordinates; keep the PRPP alternate out of an initial RKa block.",
                             "Require original free strict/ultrastrict replay, positivity and balances; protect all55 with source aliases flagged and inspect each adenylate plus H and A.",
                             "Never treat later historically exposed times as blind validation."],
            "groups": groups,
            "hold_or_separate": {
                "VAK": "ATP/ADP/AMP partition only: coefficient H=A=0. AK-down changed partition but failed off-target guards.",
                "VGAPDH_VPGK_VDPGM_VPK_VPEP_PASE": "Supply or routing, not demand. Track B13PG and PEP competition separately.",
                "VSAM": "Direct A exit, but retain sealed half-step value; downstream SAH/ADO can recycle.",
                "VAMPD1_VAMP_NT": "A exits, not direct ATP/H demand; AMP_NT dormant.",
                "VGLUCYS_VGSS_VOPLAH": "Hydrolysis-coupled GSH/oxoproline network. Serial GLUCYS/GSS not independent demand savings; OPLAH fixed.",
                "VAK2_VGMPK_VGMPS_VGLNS": "Smaller terms or coupled salvage; not priority starts.",
                "VHK": "Hold first; GLC uptake utilization and G6P need protection."}}


def build():
    frozen, factorial = verify_inputs(BASE), verify_inputs(FACTORIAL)
    verify_manifest(BASE)
    verify_manifest(FACTORIAL)
    check_seal(COMPARISON)
    receipt = read(COMPARISON / "verification.json")
    require(receipt["verified"] and receipt["archive_manifest_sha256"] == sha(FACTORIAL / "manifest.json"),
            "factorial comparison not linked to sealed replay")
    comparison = read(COMPARISON / "comparison.json")
    obs = read(BASE / "observations.json")
    identity = json.loads(json.dumps(source_audit()))
    require(identity == factorial["observation_identity"] == comparison["source_identity"]
            and identity["matching_numeric_cells"] == 770 and len(obs["values"]) == 55,
            "original Sheet1 or interpretation contract changed")
    require(obs == read(FACTORIAL / "observations.json")
            and all(frozen[k] == factorial[k] for k in ("initial", "kinetics", "numeric")),
            "unmatched initial or numerical context")
    p = frozen["cases"]["joint_half"]["parameters"]
    require(frozen["end_day"] == 46 and p == factorial["cases"]["baseline"]["parameters"],
            "expected half-step J46 as shared baseline")
    numeric = frozen["numeric"]
    require(numeric["availability_threshold_mM"] == .001 and numeric["positivity_policy"] == "reaction_consistent",
            "changed reaction availability policy")
    profiles = ("strict", "ultrastrict")
    require(tuple(frozen["design"]["profiles"]) == profiles == tuple(factorial["design"]["profiles"]),
            "unmatched profiles")
    network = phase_matrix(numeric["hematocrit"], p.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    names, rs, _, _, _ = network
    require(all(frozen["initial"][names.index(k)] == v[0] for k, v in obs["values"].items()),
            "exact55 J1 differs from original source")
    cases, rows, checks, deltas, replay_hashes = {}, [], {}, {}, {}
    factors = ((1., 1.), (1.5, 1.), (1., .5), (1.5, .5))
    for label, (gap, ak) in zip(LABELS, factors):
        original = "baseline" if label == "half_step" else label
        expected = dict(p)
        for key, factor in (("vmax_VGAPDH", gap), ("vmax_VAK", ak), ("vmax_VAK_rev", ak)):
            if factor != 1:
                expected[key] = factorial["capacities"][key] * factor
        case = factorial["cases"][original]
        require(case["parameters"] == expected and case["glucose_kinetics"] == frozen["kinetics"]
                and case["factors"] == [gap, ak] and comparison["cases"][original]["numerical_pass"],
                "comparison altered parameters outside the declared factorial")
        folder, end = (BASE, 46) if label == "half_step" else (FACTORIAL / "audits" / f"{label}_J4", 4)
        if end == 4:
            check_seal(folder)
        cases[label], checks[label], deltas[label] = {}, {}, {}
        profiles_data = []
        for profile in profiles:
            path = folder / f"J1_J{end}/glut_real_candidate_{profile}/replay.npz"
            x, daily, losses, checks[label][profile] = inspect(path, profile, end, frozen, network)
            replay_hashes[path.relative_to(ROOT).as_posix()] = sha(path)
            profiles_data.append((x, *daily.values()))
            case_windows, case_rows = ledgers(label, profile, x, daily, losses, network)
            cases[label][profile] = case_windows
            rows.extend(case_rows)
            source = comparison["cases"][original]["profiles"][profile]
            for left, right in WINDOWS[:2]:
                tag = window_id(left, right)
                for k in KINDS:
                    z = daily[k][:, :, left-1:right-1].sum(axis=2)
                    sealed = source["budgets"][tag][k+"_integrals"]
                    require(close(z[0]-z[1], [sealed[r] for r in rs], numeric, "quadrature").all(),
                            f"sealed comparison ledger mismatch: {label}/{profile}/{tag}/{k}")
            require(np.array_equal(x[[names.index(k) for k in comparison["pool_order"]], 3], source["J4_prediction_mM"]),
                    "sealed comparison J4 predictions differ")
            if label != "half_step":
                deltas[label][profile] = {"windows": matched_delta(cases["half_step"][profile], case_windows),
                                          "sealed_J4_guard": source["guard"]}
        parity = [close(a, b, numeric, "comparison") for a, b in zip(*profiles_data)]
        require(all(v.all() for v in parity), f"cross-tolerance directional comparison fails: {label}")
        checks[label]["cross_tolerance_checks"] = sum(int(v.size) for v in parity)
    deltas.pop("half_step")
    groups = priority_groups(p, cases["half_step"]["ultrastrict"], rows, network)
    summary = {
        "schema_version": 1, "source_identity": identity, "replay_sha256": replay_hashes,
        "seal_sha256": {str(f.relative_to(ROOT)): sha(f) for f in (
            BASE / "manifest.json", BASE / "source_seal.json", FACTORIAL / "manifest.json",
            FACTORIAL / "source_seal.json", COMPARISON / "files_seal.json")},
        "reference_case": "half_step", "exact_J1_source_values": 55, "all_initial_states_exact": len(frozen["initial"]),
        "comparison_supported_windows": [window_id(*w) for w in WINDOWS[:2]],
        "comparison_unavailable_windows": [window_id(*w) for w in WINDOWS[2:]],
        "optimizer_run": False, "new_ODE_integrations": 0, "biological_validation": False,
        "definitions": {
            "units": "ATP, H and A in cell-phase model mM, not bag-volume mM; extents use native reaction volume basis.",
            "H": "ATP + 0.5 ADP; not total high-energy phosphate, includes neither GTP nor phosphorylated metabolites.",
            "A": "ATP + ADP + AMP; not the total adenine-moiety inventory.",
            "signed_directions": "Forward and reverse are sign splits of archived net rates at quadrature nodes, not gross microscopic exchange.",
            "raw": "Unlimited kinetic rates evaluated on the executed trajectory; not a counterfactual trajectory.",
            "ATP_consumption": "Gross negative ATP terms include reverse ATP production reactions and transfers; not all ATP hydrolysis.",
            "hydrolysis": "Only assigned to annotated ATP-cleavage or hydrolysis-coupled chemistry, not inferred from ATP loss alone.",
            "stock_dependence": "Net endpoint stock drawdown divided by executed outflow; accounting, not tracer provenance or a flux sensitivity.",
            "pool_exit": "A exits to another modeled form can recycle; not necessarily physical loss.",
            "compensation": "Compare separate production and consumption changes; overlap is arithmetic, not proof of causal feedback.",
        },
        "checks": checks, "cases": cases, "matched_deltas_vs_half_step": deltas,
        "coupled_admitted_in_sealed_J4_comparison": comparison["coupled_admitted"],
    }
    return summary, groups, rows


def artifacts(summary, groups, rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["case", "profile", "window", "kind", "reaction", "mechanism",
                     *(f"{p}_coefficient" for p in METRICS),
                     "forward_extent_mM", "reverse_extent_mM", "signed_extent_mM",
                     *(f"{p}_{k}_mM" for p in METRICS for k in ("production", "consumption", "net"))])
    writer.writerows(rows)
    return {"reaction_ledger.csv": buffer.getvalue(),
            "summary.json": json.dumps(summary, indent=2, allow_nan=False)+"\n",
            "priority_vmax_groups.json": json.dumps(groups, indent=2, allow_nan=False)+"\n"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="rebuild in memory and check the existing artifacts")
    args = parser.parse_args()
    if not args.verify:
        require(not DEST.exists(), f"refusing to overwrite {DEST}")
    with threadpool_limits(1):
        summary, groups, rows = build()
    contents = artifacts(summary, groups, rows)
    if args.verify:
        require({p.name for p in DEST.iterdir()} == {*contents, "files_seal.json"}, "unexpected output set")
        check_seal(DEST)
        for name, expected in contents.items():
            require((DEST / name).read_text(encoding="utf-8") == expected, f"artifact reproduction failed: {name}")
    else:
        DEST.mkdir()
        for name, body in contents.items():
            (DEST / name).write_text(body, encoding="utf-8", newline="\n")
        seal = {name: sha(DEST / name) for name in contents}
        (DEST / "files_seal.json").write_text(json.dumps(seal, indent=2)+"\n", encoding="utf-8")
        check_seal(DEST)
    print(f"{'Verified' if args.verify else 'Wrote'} {len(rows)} reaction rows and {len(groups['groups'])} Vmax groups: {DEST}")


if __name__ == "__main__":
    main()
