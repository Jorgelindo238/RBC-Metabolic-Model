"""Audit executed B13PG/ATP budgets on the converged provisional FLA profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(path))

from audit_ppp_constraints_and_numerics import file_hash, write_json
from equadiff_brodbar import equadiff_brodbar
from fla_balance_audit import accepted_step_quadrature, integrate_intervals
from fla_executed_attribution import aggregate_windows, limiting_loss_attribution, signed_pool_contributions
from fla_working_reference import DEFAULT_WORKING_REFERENCE, load_working_reference, reference_options
from reaction_positivity import rbc_reaction_matrix
from test_reaction_positivity_fixed_context import POLICY, load_context, replay
from verify_fla_working_reference import compare_arrays

DEFAULT_SOURCE = ROOT / "output/fla_working_reference_verification_2026_10_05"
DEFAULT_OUT = ROOT / "output/b13pg_atp_executed_audit_2026_10_05"
POOLS = ("B13PG", "ATP", "ADP", "B23PG")
LIMITED_REACTIONS = ("VPGK", "VDPGM", "VGAPDH", "VPK", "VHK", "VPFK", "VAK", "VNDPK")
WINDOWS = (("J1_J1.1", 1., 1.1), ("J1.1_J1.3", 1.1, 1.3), ("J1.3_J1.6", 1.3, 1.6),
           ("J1.6_J2", 1.6, 2.), ("J2_J3", 2., 3.), ("J1_J3", 1., 3.),
           ("J3_J10", 3., 10.), ("J10_J46", 10., 46.), ("J1_J46", 1., 46.))


def integrands(parts, states, names, reactions, matrix, threshold):
    rows, meta = [], []
    for pool in POOLS:
        index = names.index(pool)
        for reaction in np.flatnonzero(matrix[index]):
            rows.append((index, reaction, matrix[index, reaction]))
            meta.append((pool, reactions[reaction]))
    raw = np.asarray([coefficient * parts["native_flux"][reaction] for _, reaction, coefficient in rows])
    effective = np.asarray([coefficient * parts["effective_flux"][reaction] for _, reaction, coefficient in rows])
    signed = signed_pool_contributions(np.ones(len(rows)), effective)
    indices = [names.index(pool) for pool in POOLS]
    values = {"native_contribution": raw, "executed_contribution": effective,
              "production": signed["production"], "consumption": signed["consumption"],
              "modifier_contribution": effective - raw,
              "rhs": parts["executed"][indices], "nonreaction_residual": parts["nonreaction_residual"][indices]}
    losses, loss_meta, total = [], [], []
    for name in LIMITED_REACTIONS:
        index = reactions.index(name)
        attribution = limiting_loss_attribution(states[:113], parts["native_flux"][index], matrix[:, index], threshold=threshold)
        np.testing.assert_allclose(attribution["factors"], parts["availability_factors"][index], rtol=0, atol=1e-14)
        total.append(attribution["loss"])
        for pool in np.flatnonzero(matrix[:, index]):
            losses.append(attribution["loss_by_pool"][pool])
            loss_meta.append((name, names[pool]))
    values["limiter_loss_by_pool"], values["limiter_loss"] = np.asarray(losses), np.asarray(total)
    labels = {key: [f"{pool}:{reaction}" for pool, reaction in meta] for key in
              ("native_contribution", "executed_contribution", "production", "consumption", "modifier_contribution")}
    labels.update(rhs=list(POOLS), nonreaction_residual=list(POOLS), limiter_loss=list(LIMITED_REACTIONS),
                  limiter_loss_by_pool=[f"{reaction}:{pool}" for reaction, pool in loss_meta])
    return values, meta, loss_meta, labels


def summarize_windows(integrals, boundaries, solution, meta, loss_meta):
    aggregated = {key: aggregate_windows(value, boundaries, WINDOWS) for key, value in integrals.items()}
    reaction_rows, pool_rows, loss_rows = [], [], []
    for window_index, (window, start, end) in enumerate(WINDOWS):
        for index, (pool, reaction) in enumerate(meta):
            reaction_rows.append({"window": window, "start_day": start, "end_day": end, "pool": pool,
                "reaction": reaction, **{f"{key}_mM": float(aggregated[key][index, window_index]) for key in
                 ("native_contribution", "executed_contribution", "production", "consumption", "modifier_contribution")}})
        for index, pool in enumerate(POOLS):
            members = [j for j, (name, _) in enumerate(meta) if name == pool]
            state_index = rbc_reaction_matrix()[0].index(pool)
            delta = float(solution.sol(end)[state_index] - solution.sol(start)[state_index])
            net = float(aggregated["executed_contribution"][members, window_index].sum())
            pool_rows.append({"window": window, "pool": pool, "start_day": start, "end_day": end,
                "state_start_mM": float(solution.sol(start)[state_index]), "state_end_mM": float(solution.sol(end)[state_index]),
                "state_change_mM": delta, "executed_net_mM": net,
                "production_mM": float(aggregated["production"][members, window_index].sum()),
                "consumption_mM": float(aggregated["consumption"][members, window_index].sum()),
                "native_net_mM": float(aggregated["native_contribution"][members, window_index].sum()),
                "nonreaction_residual_mM": float(aggregated["nonreaction_residual"][index, window_index]),
                "solver_integral_residual_mM": delta - float(aggregated["rhs"][index, window_index].sum()),
                "state_minus_reaction_integral_mM": delta - net})
        for index, (reaction, pool) in enumerate(loss_meta):
            amount = float(aggregated["limiter_loss_by_pool"][index, window_index])
            total = float(aggregated["limiter_loss"][LIMITED_REACTIONS.index(reaction), window_index])
            loss_rows.append({"window": window, "reaction": reaction, "limiting_pool": pool,
                              "allocated_absolute_rate_loss_mM": amount,
                              "total_absolute_rate_loss_mM": total,
                              "loss_share": amount / total if total > 0 else None})
    return pd.DataFrame(reaction_rows), pd.DataFrame(pool_rows), pd.DataFrame(loss_rows)


def sample_frame(solution, params, ode, names, reactions, matrix, times):
    time = np.unique(np.r_[solution.t, times, np.linspace(1, 46, 901), 1 + np.geomspace(1e-9, 2, 101)])
    states = solution.sol(time)
    parts = replay(time, states, params, ode["positivity_policy"], reactions, matrix,
                   threshold=ode["reaction_availability_threshold"])
    frame = {"time_day": time}
    for pool in ("B13PG", "B23PG", "ATP", "ADP", "AMP", "GA3P", "G6P", "PEP", "NAD", "NADH"):
        frame[pool] = states[names.index(pool)]
    for pool in POOLS:
        index = names.index(pool)
        for key in ("native_balance", "effective_balance", "executed", "nonreaction_residual"):
            frame[f"{pool}_{key}"] = parts[key][index]
    for reaction in sorted(set(LIMITED_REACTIONS) | {reactions[j] for j in np.flatnonzero(matrix[names.index("ATP")])}):
        index = reactions.index(reaction)
        for key in ("native_flux", "effective_flux", "availability_factors"):
            frame[f"{reaction}_{key}"] = parts[key][index]
    atp = signed_pool_contributions(matrix[names.index("ATP")], parts["effective_flux"])
    frame["ATP_production"], frame["ATP_consumption"] = atp["production"].sum(axis=0), atp["consumption"].sum(axis=0)
    ratio = np.maximum(frame["NAD"], 1e-6) / (np.maximum(frame["NADH"], 1e-6) + 1e-6)
    frame["native_GAPDH_redox_ratio"] = ratio
    km = float(params.get("km_NAD_NADH", 1.0))
    frame["native_GAPDH_redox_mm_factor"] = ratio / (km + ratio + 1e-30)
    return pd.DataFrame(frame), float(np.min(states[:113])), float(np.max(np.abs(parts["nonreaction_residual"])))


def experimental_intervals(integrals, boundaries, solution, meta, times, curves):
    windows = [(str(i), float(start), float(end)) for i, (start, end) in enumerate(zip(times[:-1], times[1:]))]
    values = aggregate_windows(integrals["executed_contribution"], boundaries, windows)
    rows = []
    for pool in ("ATP", "ADP", "B23PG"):
        members = [i for i, (name, _) in enumerate(meta) if name == pool]
        for index, (_, start, end) in enumerate(windows):
            change = float(curves[pool][index + 1] - curves[pool][index])
            net = float(values[members, index].sum())
            conditional = None
            if pool == "ATP":
                pgk = meta.index(("ATP", "VPGK"))
                conditional = change - (net - float(values[pgk, index]))
            rows.append({"pool": pool, "start_day": start, "end_day": end,
                         "reference_state_change_mM": change, "executed_net_integral_mM": net,
                         "reference_minus_executed_mM": change - net,
                         "conditional_required_VPGK_mM": conditional,
                         "individual_flux_identified": False})
    return pd.DataFrame(rows)


def audit_solution(solution, params, ode, directory, names, reactions, matrix, times, curves):
    directory.mkdir()
    cuts = np.unique(np.r_[times, [start for _, start, _ in WINDOWS], [end for _, _, end in WINDOWS]])
    sample, minimum, closure = sample_frame(solution, params, ode, names, reactions, matrix, times)
    sample.to_csv(directory / "executed_timeseries.csv", index=False)
    np.savez_compressed(directory / "accepted_solver_states.npz", time=solution.t, states=solution.y)
    integrals = {}
    for order in (4, 8):
        grid = accepted_step_quadrature(solution.t, cuts, order=order)
        if len(grid.nodes) > POLICY["maximum_quadrature_nodes"]:
            raise ValueError("predeclared quadrature node budget exceeded")
        states = solution.sol(grid.nodes)
        parts = replay(grid.nodes, states, params, ode["positivity_policy"], reactions, matrix,
                       threshold=ode["reaction_availability_threshold"])
        values, meta, loss_meta, labels = integrands(parts, states, names, reactions, matrix, ode["reaction_availability_threshold"])
        integrals[order] = {key: integrate_intervals(value, grid) for key, value in values.items()}
        minimum = min(minimum, float(np.min(states[:113])))
        closure = max(closure, float(np.max(np.abs(parts["nonreaction_residual"]))))
    checks = []
    for key in integrals[8]:
        difference, passed = compare_arrays(integrals[4][key], integrals[8][key],
            atol=POLICY["quadrature_absolute_tolerance_mM"], rtol=POLICY["quadrature_relative_tolerance"])
        checks.extend({"quantity": key, "name": label, "passes": bool(passed[index]),
                       "maximum_difference_mM": float(difference[index])} for index, label in enumerate(labels[key]))
    check_frame = pd.DataFrame(checks)
    check_frame.to_csv(directory / "quadrature_checks.csv", index=False)
    fine = integrals[8]
    np.savez_compressed(directory / "interval_integrals.npz", boundaries=cuts, **fine,
                        **{f"{key}_labels": labels[key] for key in fine})
    reaction_rows, pool_rows, loss_rows = summarize_windows(fine, cuts, solution, meta, loss_meta)
    reaction_rows.to_csv(directory / "window_reaction_contributions.csv", index=False)
    pool_rows.to_csv(directory / "window_pool_budgets.csv", index=False)
    loss_rows.to_csv(directory / "window_limiter_attribution.csv", index=False)
    experimental_intervals(fine, cuts, solution, meta, times, curves).to_csv(directory / "experimental_intervals.csv", index=False)
    summary = {"minimum_raw_checked_concentration_mM": minimum, "max_executed_closure_mM_per_day": closure,
        "negative_accepted_count": int(np.count_nonzero(solution.y[:113] < 0)),
        "quadrature_check_count": len(checks), "failed_quadrature_checks": int((~check_frame.passes).sum()),
        "max_window_solver_integral_residual_mM": float(pool_rows.solver_integral_residual_mM.abs().max()),
        "numerical_integrity_pass": bool(minimum >= POLICY["minimum_raw_state_mM"] and closure <= POLICY["closure_tolerance_mM_per_day"] and check_frame.passes.all())}
    write_json(directory / "summary.json", summary)
    return {"solution": solution, "integrals": fine, "labels": labels, "cuts": cuts, "meta": meta,
            "sample": sample, "reactions": reaction_rows, "pools": pool_rows, "losses": loss_rows, "summary": summary}


def cached_threshold_budgets(source, names, reactions, matrix):
    rows = []
    windows = [window for window in WINDOWS if window[0] in {"J1_J3", "J3_J10", "J10_J46", "J1_J46"}]
    for threshold in (1e-4, 1e-3, 1e-2):
        directory = source / f"tau_{threshold:.0e}_ultrastrict"
        with np.load(directory / "quadrature_integrals.npz") as data:
            for key in ("native_flux", "effective_flux"):
                aggregated = aggregate_windows(data[key], data["boundaries"], windows)
                for pool in POOLS:
                    index = names.index(pool)
                    for reaction in np.flatnonzero(matrix[index]):
                        for window_index, (window, _, _) in enumerate(windows):
                            rows.append({"threshold_mM": threshold, "window": window, "pool": pool,
                                "reaction": reactions[reaction], "rate_kind": key,
                                "signed_pool_contribution_mM": float(matrix[index, reaction] * aggregated[reaction, window_index])})
    return pd.DataFrame(rows)


def plot_audit(out_dir, result, times, curves):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 2, figsize=(13, 10), constrained_layout=True)
    data = result["sample"]
    for axis, pool in zip(axes[0], ("ATP", "B13PG")):
        axis.plot(data.time_day, data[pool], color="#147d78", label="Executed strict replay")
        if pool == "ATP":
            axis.scatter(times, curves[pool], color="#333333", s=22, label="Local reference table", zorder=3)
        axis.set(title=pool, xlabel="Model day", ylabel="Concentration (mM, log scale)", yscale="log")
        axis.legend(fontsize=8)
    early = data.loc[data.time_day <= 3]
    for reaction, color in zip(("VGAPDH", "VPGK", "VDPGM"), ("#147d78", "#3657ad", "#bd5961")):
        axes[1, 0].plot(early.time_day, early[f"{reaction}_effective_flux"], label=reaction, color=color)
    axes[1, 0].set(title="Executed B13PG supply and drains", xlabel="Model day", ylabel="Net reaction rate (mM/day)")
    axes[1, 0].legend(fontsize=8)
    for name, color in (("production", "#147d78"), ("consumption", "#bd5961")):
        axes[1, 1].plot(early.time_day, early[f"ATP_{name}"], label=name.capitalize(), color=color)
    axes[1, 1].set(title="ATP contributions split by actual sign", xlabel="Model day", ylabel="Pool rate (mM/day)")
    axes[1, 1].legend(fontsize=8)
    sinks = result["reactions"].loc[lambda x: x.window.eq("J1_J3") & x.pool.eq("ATP")].nlargest(7, "consumption_mM").sort_values("consumption_mM")
    axes[2, 0].barh(sinks.reaction, sinks.consumption_mM, color="#bd5961")
    axes[2, 0].set(title="Executed ATP consumption: J1-J3", xlabel="Integrated ATP consumption (mM)")
    loss = result["losses"].loc[lambda x: x.window.eq("J1_J46") & x.reaction.eq("VPGK") & x.allocated_absolute_rate_loss_mM.gt(1e-12)]
    axes[2, 1].barh(loss.limiting_pool, loss.allocated_absolute_rate_loss_mM, color="#3657ad")
    axes[2, 1].set(title="PGK rate reduction by limiting consumer: J1-J46", xlabel="Allocated native-executed rate loss (mM)")
    for axis in axes.flat:
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(alpha=.15)
    fig.suptitle("Fixed kinetics: executed B13PG-ATP attribution, not calibration", fontsize=14)
    fig.savefig(out_dir / "executed_b13pg_atp_audit.png", dpi=180)
    fig.savefig(out_dir / "executed_b13pg_atp_audit.pdf")
    plt.close(fig)


def run(source, out_dir):
    if out_dir.exists():
        raise FileExistsError("use a fresh output directory; archived audits cannot be overwritten")
    config = load_working_reference()
    prior = json.loads((source / "preregistered_contract.json").read_text())
    prior_summary = json.loads((source / "summary.json").read_text())
    if prior["working_reference"] != config or not prior_summary["reference_numerical_convergence_passes"]:
        raise ValueError("source must be the converged, unchanged working profile")
    for filename, digest in prior["input_sha256"].items():
        if file_hash(Path(filename)) != digest:
            raise ValueError(f"source changed since numerical verification: {filename}")
    x0, params, names, times, curves, data_path = load_context(ROOT / config["fixed_context"])
    _, reactions, matrix = rbc_reaction_matrix(params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    for filename, key in (("fixed_parameters.json", "fixed_parameter_sha256"), ("fixed_initial_state.csv", "initial_state_sha256")):
        if file_hash(source / filename) != prior[key]:
            raise ValueError("verified frozen snapshot changed")
    out_dir.mkdir(parents=True)
    inputs = [DEFAULT_WORKING_REFERENCE, data_path, source / "preregistered_contract.json", source / "summary.json",
              ROOT / "src/fla_executed_attribution.py", Path(__file__)]
    for directory in sorted(path for path in source.glob("tau_*") if path.is_dir()):
        inputs.extend(directory / filename for filename in ("summary.json", "quadrature_integrals.npz", "accepted_solver_states.npz"))
    write_json(out_dir / "preregistered_contract.json", {"working_reference": config, "source": str(source.resolve()),
        "input_sha256": {str(path.resolve()): file_hash(path) for path in inputs},
        "fixed_parameter_sha256": prior["fixed_parameter_sha256"], "initial_state_sha256": prior["initial_state_sha256"],
        "windows": WINDOWS, "pools": POOLS, "limited_reactions": LIMITED_REACTIONS, "quadrature_policy": POLICY,
        "observation_resets": False, "optimization_performed": False, "parameters_promoted": False,
        "threshold_fitted": False, "B13PG_independent_teacher": False,
        "limiter_attribution": "absolute rate loss allocated to minimum consumers; ties split equally; not a causal intervention"})
    cached_threshold_budgets(source, names, reactions, matrix).to_csv(out_dir / "cached_threshold_signed_budgets.csv", index=False)
    results = {}
    for label in ("strict", "ultrastrict"):
        ode, solver = reference_options(config, ultrastrict=label == "ultrastrict")
        print(f"[{label}] reproduce continuous J1-J46 and audit executed signed budgets", flush=True)
        solution = solve_ivp(lambda day, state: equadiff_brodbar(float(day), state, custom_params=params, **ode),
                             (1., 46.), x0.copy(), dense_output=True, **solver)
        if not solution.success or not np.all(np.isfinite(solution.y)):
            raise RuntimeError(solution.message)
        with np.load(source / f"tau_1e-03_{label}/accepted_solver_states.npz") as saved:
            if not np.array_equal(solution.t, saved["time"]) or not np.array_equal(solution.y, saved["states"]):
                raise ValueError("fresh replay must reproduce verified time/state arrays bit-for-bit")
        results[label] = audit_solution(solution, params, ode, out_dir / label, names, reactions, matrix, times, curves)
        results[label]["summary"]["reproduces_verified_solver_arrays_bit_exactly"] = True
        write_json(out_dir / label / "summary.json", results[label]["summary"])
        print(f"[{label}] quadrature failures={results[label]['summary']['failed_quadrature_checks']}", flush=True)
    comparisons = []
    for key in results["strict"]["integrals"]:
        difference, passed = compare_arrays(results["strict"]["integrals"][key], results["ultrastrict"]["integrals"][key],
                                            atol=1e-5, rtol=.01)
        comparisons.extend({"quantity": key, "name": name, "passes": bool(passed[index]),
                            "maximum_difference_mM": float(difference[index])}
                           for index, name in enumerate(results["strict"]["labels"][key]))
    comparisons = pd.DataFrame(comparisons)
    comparisons.to_csv(out_dir / "strict_ultrastrict_attribution_comparison.csv", index=False)
    summary = {"cases": {label: value["summary"] for label, value in results.items()},
        "comparison_count": len(comparisons), "failed_solver_comparisons": int((~comparisons.passes).sum()),
        "numerical_audit_passes": bool(comparisons.passes.all() and all(value["summary"]["numerical_integrity_pass"] for value in results.values())),
        "kinetics_changed": False, "parameters_promoted": False, "calibration_allowed": False,
        "B13PG_independent_teacher": False, "conditional_ATP_requirement_is_not_an_observed_VPGK": True,
        "next_execution": "review executed ATP sinks, B13PG drainage and ADP availability, then freeze data/absolute-accuracy contracts before a dynamic sensitivity screen"}
    write_json(out_dir / "summary.json", summary)
    plot_audit(out_dir, results["strict"], times, curves)
    lines = ["# Executed B13PG-ATP audit", "", "## Scope", "",
        "Fixed unpromoted kinetic context, reaction_consistent, threshold 1e-3 mM. Strict/ultrastrict J1-J46 solutions reproduce the preceding numerical-verification arrays bit-for-bit. No kinetic fitting, forcing, state resets or output projection.", "",
        "dB13PG/dt = VGAPDH_exec - VPGK_exec - VDPGM_exec; dB23PG/dt = VDPGM_exec - V23DPGP_exec. ATP and ADP use all nonzero terms of the corrected matrix. Contributions are split by the sign of S_ij*v_exec BEFORE integration, including reversible AK/NDPK. This is not thermodynamic gross forward/reverse exchange.", "",
        "The native-rate counterfactual is evaluated at the same executed trajectory. Limiter loss is assigned to minimum-availability consumers, with ties split equally; this is descriptive accounting, not a causal intervention. B13PG is quarantined as an independent reference teacher because it duplicates B23PG in the local table.", "",
        "## Numerical checks", "", f"Attribution numerical gate passes: {summary['numerical_audit_passes']}. Strict/ultrastrict failed comparisons: {summary['failed_solver_comparisons']}/{summary['comparison_count']}.", "",
        "## Strict pool budgets", "", "| Window | Pool | Production (mM) | Consumption (mM) | State change (mM) | Solver residual (mM) |", "|---|---|---:|---:|---:|---:|"]
    for row in results["strict"]["pools"].itertuples():
        if row.window in {"J1_J3", "J1_J46"}:
            lines.append(f"| {row.window} | {row.pool} | {row.production_mM:.8g} | {row.consumption_mM:.8g} | {row.state_change_mM:.8g} | {row.solver_integral_residual_mM:.3g} |")
    lines += ["", "## Evidence and interpretation limits", "",
        "window_reaction_contributions.csv contains every stoichiometric ATP/ADP/B13PG/B23PG term, its native/executed pair, actual-sign production/consumption and modifier contribution. window_limiter_attribution.csv records PGK/DPGM/GAPDH/PK/HK/PFK/AK/NDPK reductions by limiting consumer. Overlapping windows are separate summaries and must not be summed as independent periods.", "",
        "experimental_intervals.csv compares exact tabulated concentration changes with executed integrals, not sampled derivative estimates. Conditional ATP-required VPGK is computed holding all other simulated ATP terms fixed: it is not an individually observed flux, a causal intervention or a fitting target. There is no measured postinitial J1-J3 endpoint and none is invented.", "",
        "cached_threshold_signed_budgets.csv carries the three previously converged ultrastrict thresholds, with signed native/executed contributions. Those cached net integrals do not reconstruct positive/negative gross contributions. Thresholds are not selected by predictive loss. Raw data provenance and absolute accuracy limits remain unresolved. Numerical closure cannot establish biological calibration."]
    (out_dir / "decision_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out_dir / "decision_report.md"), "numerical_audit_passes": summary["numerical_audit_passes"]}), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(args.source, args.out_dir)
