"""Present complete conditional energy responses, without best-case selection."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "output/exploratory_energy_sensitivity_J1_J4_2026_10_06"
GROUPS = ("investment", "AK_capacity", "GAPDH_PGK_capacity")
COLORS = ("#168578", "#ad3858", "#467fb2", "#9d780f")


def finalize(out):
    summary = json.loads((out / "summary.json").read_text())
    plan = json.loads((out / "exploratory_probe_plan.json").read_text())
    endpoints = pd.read_csv(out / "J4_endpoint_diagnostics.csv", float_precision="round_trip")
    singles = pd.read_csv(out / "single_group_responses.csv", float_precision="round_trip")
    interactions = pd.read_csv(out / "paired_group_interactions.csv", float_precision="round_trip")
    observed = endpoints[(endpoints.case == "baseline")&(endpoints.solver == "strict")].set_index("pool")
    fig, axes = plt.subplots(3, 3, figsize=(13, 9), constrained_layout=True)
    for column, group in enumerate(GROUPS):
        cases = [c for c in plan["cases"] if len(c["log_scales"]) == 1 and group in c["log_scales"]]
        for row, pool in enumerate(("ATP", "ADP", "AMP")):
            axis = axes[row, column]
            for case, color in zip([plan["cases"][0]]+cases, ["#222222"]+list(COLORS)):
                frame = pd.read_csv(out / f"{case['case_id']}_strict" / "executed_timeseries.csv")
                scale = case["log_scales"].get(group, 0.)
                label = "baseline" if scale == 0 else f"capacity x {np.exp(scale):.3f}"
                axis.plot(frame.time_day, frame[pool], color=color, linewidth=1.3, label=label,
                          linestyle="-" if scale >= 0 else "--")
            initial = np.load(out / "frozen_initial_state.npz")
            y1 = initial["states"][list(initial["names"]).index(pool)]
            axis.scatter([1., 4.], [y1, observed.loc[pool, "reference_J4_mM"]], color="#111111", marker="o", s=20, zorder=5,
                         label="_nolegend_")
            axis.set(xlabel="Model day", ylabel=f"{pool} (nominal mM)")
            if row == 0:
                axis.set_title(group.replace("_", " "))
                axis.legend(fontsize=7, frameon=False, loc="upper right")
            axis.spines[["top", "right"]].set_visible(False)
            axis.grid(alpha=.15)
    fig.suptitle("Conditional energy sensitivity: exact observed J1, no calibration\nBlack markers: nominal workbook endpoints", fontsize=12)
    fig.savefig(out / "single_group_adenylate_trajectories.png", dpi=170)
    fig.savefig(out / "single_group_adenylate_trajectories.pdf")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), constrained_layout=True)
    for axis, pool in zip(axes, ("ATP", "ADP", "AMP")):
        selected = singles[(singles.solver == "strict")&(singles.kind == "J4_concentration")&(singles.name == pool)]
        positions = np.arange(3)
        for j, (step, color) in enumerate(((.05, "#168578"), (.10, "#ad3858"))):
            values = selected[selected.log_step == step].set_index("group").loc[list(GROUPS), "response_per_log_capacity"]
            axis.bar(positions+(-.18 if j == 0 else .18), values, width=.34, color=color, label=f"log step {step}")
        axis.axhline(0., color="#333333", linewidth=.7)
        axis.set(xticks=positions, xticklabels=["HK / PFK", "AK", "GAPDH / PGK"], ylabel="J4 response (mM / log capacity)", title=pool)
        axis.spines[["top", "right"]].set_visible(False)
        axis.legend(frameon=False, fontsize=8)
    fig.suptitle("Signed local responses; not parameter rankings or biological error limits", fontsize=12)
    fig.savefig(out / "signed_endpoint_responses.png", dpi=170)
    fig.savefig(out / "signed_endpoint_responses.pdf")
    plt.close(fig)

    baseline = pd.read_csv(out / "baseline_strict" / "executed_timeseries.csv")
    lines = ["# Conditional exploratory energy sensitivity: steps 1-3", "",
        "User-authorized exploratory branch, not execution of the blocked historical biological protocol. No optimizer, best-case ranking, model promotion, observation reset, teacher forcing or artificial ATP source.", "",
        "## Initialization and scope", "",
        "All 55 nominal Sheet1 J1 entries initialize their exact mapped states, including zeros. Every unmeasured pool retains the frozen context. NAD=NADH=1 mM remains an unverified model assumption; Initial_conditions_JA_Final.xls is not loaded for initialization. The full 114-state ODE uses the unchanged reaction_consistent BDF strict/ultrastrict profile and 1e-3 mM availability threshold.", "",
        "Changes relative to the earlier archived context are explicitly isolated: B13PG 0.000176677669 -> 3.584045211 nominal mM, ECYS/EINO 1e-6 -> 0. B13PG/B23PG and P2G/P3G are duplicate source signals and not independent validation channels. The new baseline is not silently substituted into historical replays.", "",
        "Eleven baseline/single-group configurations and eight paired configurations give 38 integrations on J1-J4. HK/PFK are downward-only; AK forward/reverse capacities scale together; GAPDH/PGK capacities scale together. Single log steps 0.05/0.10 correspond to numerical probes, not physiological parameter ranges. All other kinetics and latent initial states are fixed.", "",
        "## Numerical verification", "",
        f"Completed integrations: {summary['integrations_completed']}/38. Numerical diagnostic gate: {summary['numerical_diagnostic_passes']}. Quadrature failures: {summary['failed_quadrature_checks']}/{summary['quadrature_check_count']}; strict/ultrastrict failures: {summary['failed_convergence_checks']}/{summary['convergence_check_count']}. Minimum checked raw concentration: {summary['minimum_raw_checked_concentration_mM']:.9g} nominal mM.",
        "Convergence and positivity apply to this conditional context and checked states, not universal solver behavior or biological validity. Independent verification and QA are recorded in their separate receipts.", "",
        "## Baseline J4 partition", "", "| Pool | Simulated | Nominal reference |", "|---|---:|---:|"]
    for pool in ("ATP", "ADP", "AMP"):
        lines.append(f"| {pool} | {observed.loc[pool, 'model_J4_mM']:.9g} | {observed.loc[pool, 'reference_J4_mM']:.9g} |")
    reference = [observed.loc[p, "reference_J4_mM"] for p in ("ATP", "ADP", "AMP")]
    reference_charge = (reference[0]+.5*reference[1])/sum(reference)
    lines += [f"| Total | {baseline.ATP_ADP_AMP.iloc[-1]:.9g} | {sum(reference):.9g} |",
              f"| Energy charge | {baseline.energy_charge.iloc[-1]:.9g} | {reference_charge:.9g} |", "",
        "## Baseline executed J1-J4 budgets", "",
        "| Pool | Reference increment | Executed net | Production | Consumption |", "|---|---:|---:|---:|---:|"]
    budgets = pd.read_csv(out / "baseline_strict" / "window_pool_budgets.csv")
    budgets = budgets[budgets.window == "J1_J4"].set_index("pool")
    initial = np.load(out / "frozen_initial_state.npz")
    for pool in ("ATP", "ADP", "AMP"):
        target = observed.loc[pool, "reference_J4_mM"]-initial["states"][list(initial["names"]).index(pool)]
        row = budgets.loc[pool]
        lines.append(f"| {pool} | {target:.9g} | {row.net_mM:.9g} | {row.production_mM:.9g} | {row.consumption_mM:.9g} |")
    lines += ["All quantities in this table are nominal mM. The reference increments constrain net pool balances, not each internal reaction separately. Production and consumption use actual signed stoichiometric contributions, including reversals.", "",
        "## Signed responses (strict; endpoint mM per log capacity)", "",
        "Positive response means increasing the group raises the simulated endpoint. Investment is a one-sided response at its upper boundary; for a downward perturbation its predicted change has the opposite sign. Central differences apply to AK and GAPDH/PGK. These responses include dynamic feedback and numerical-limiter action; they are not independent enzyme control measurements.", "",
        "| Group | Log step | ATP | ADP | AMP |", "|---|---:|---:|---:|---:|"]
    for group in GROUPS:
        for step in (.05, .10):
            selected = singles[(singles.solver == "strict")&(singles.group == group)&(singles.log_step == step)&(singles.kind == "J4_concentration")].set_index("name")
            lines.append(f"| {group} | {step} | " + " | ".join(f"{selected.loc[p, 'response_per_log_capacity']:.9g}" for p in ("ATP", "ADP", "AMP")) + " |")
    lines += ["", "## Paired interactions (strict; endpoint mM per squared log capacity)", "",
        "Mixed finite differences retain all required single-group/corner terms. They describe local nonadditivity at h=0.05, not a fitted joint intervention or proof of an optimal parameter combination.", "",
        "| Pair | ATP | ADP | AMP |", "|---|---:|---:|---:|"]
    for first, second in ((GROUPS[0], GROUPS[1]), (GROUPS[0], GROUPS[2]), (GROUPS[1], GROUPS[2])):
        selected = interactions[(interactions.solver == "strict")&(interactions.first_group == first)&(interactions.second_group == second)&(interactions.kind == "J4_concentration")].set_index("name")
        lines.append(f"| {first} / {second} | " + " | ".join(f"{selected.loc[p, 'mixed_response_per_log_capacity_squared']:.9g}" for p in ("ATP", "ADP", "AMP")) + " |")
    lines += ["", "## Full evidence and interpretation", "",
        "All 113 concentration trajectories, all 100 native/executed reaction rates, availability factors, executed ATP/ADP/AMP and purine/redox budgets, all nominal J4 endpoints and group/paired response vectors are retained. Source points J2/J3 are not invented. Individual internal flux integrals are model predictions, not measured teachers.",
        "Quadrature budgets use accepted-step Gauss orders 4/8. Consumer-limiter shares use a separately labeled trapezoid diagnostic on accepted-plus-dense samples; they are not independent quadrature or causal control coefficients. Native and executed rates are evaluated on the same actual trajectory.",
        "Compare both probe sizes and strict/ultrastrict responses before interpreting a small signed difference. Sensitivities may amplify solver differences; a converged trajectory is not proof that every tiny response or interaction is resolved. No significance or confidence interval follows without observation uncertainty.", "",
        "## Decision boundary", "",
        f"Scientific readiness still has {summary['scientific_blocker_count']} unmet checks. The original prepared coupled protocol remains unauthorized, with its zero-simulation historical receipt preserved. This separate exploratory result cannot set accuracy tolerances, validate units, supply redox priors or authorize biological optimization/promotion.",
        "Steps 1-3 are complete. Any J1-J10/J1-J46 extension or restricted fitting is a subsequent decision, not automatically launched. Retain measured J1, preserve unmeasured assumptions explicitly, and resolve source normalization/uncertainty/accuracy before claiming a biological calibration.", "",
        "Reproduce in a fresh directory: run_exploratory_energy_sensitivity.py, full QA with qa_results.xml, finalize_exploratory_energy_sensitivity.py, then verify_exploratory_energy_sensitivity.py.", ""]
    (out / "decision_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(str(out / "decision_report.md"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    finalize(parser.parse_args().out.resolve())
