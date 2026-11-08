"""Prepare fixed-IC local probes; no ODE execution, optimizer or candidate ranking."""

import ast
import itertools
import math
from pathlib import Path

GROUPS = {
    "investment": ("vmax_VHK", "vmax_VPFK"),
    "AK_capacity": ("vmax_VAK", "vmax_VAK_rev"),
    "GAPDH_PGK_capacity": ("vmax_VGAPDH", "vmax_VPGK"),
}
DIRECTIONS = {"investment": (-1,), "AK_capacity": (-1, 1), "GAPDH_PGK_capacity": (-1, 1)}


def resolved_parameters(parameters, kernel_path):
    """Resolve omitted kinetic defaults from the actual hashed kernel AST."""
    requested = {name for members in GROUPS.values() for name in members}
    defaults = {}
    for node in ast.walk(ast.parse(Path(kernel_path).read_text(encoding="utf-8-sig"))):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name, value = node.targets[0].id, node.value
        if (name in requested and isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id == "_get_param" and len(value.args) >= 3
                and isinstance(value.args[1], ast.Constant) and value.args[1].value == name):
            if name in defaults:
                raise ValueError(f"ambiguous default for {name}")
            defaults[name] = (ast.literal_eval(value.args[2]), node.lineno)
    result, provenance = {}, {}
    for name in sorted(requested):
        if name in parameters:
            value = parameters[name]
            provenance[name] = {"source": "frozen_parameters"}
        elif name in defaults:
            value, line = defaults[name]
            provenance[name] = {"source": "hashed_kernel_default", "path": str(Path(kernel_path).resolve()), "line": line}
        else:
            raise ValueError(f"unresolved kinetic parameter: {name}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"invalid positive capacity: {name}")
        result[name] = float(value)
    return result, provenance


def build_sensitivity_plan(resolved):
    names = {name for members in GROUPS.values() for name in members}
    if set(resolved) != names or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                    or not math.isfinite(v) or v <= 0 for v in resolved.values()):
        raise ValueError("all six positive finite capacities must be explicitly resolved")
    if resolved["vmax_VHK"] > 5.0:
        raise ValueError("frozen HK capacity exceeds the retained 5.0 ceiling")
    cases = [{"case_id": "baseline", "stage": "single_group", "log_scales": {}, "parameter_overrides": {}}]
    def add(scales, stage, suffix):
        overrides = {name: resolved[name] * math.exp(scale) for group, scale in scales.items() for name in GROUPS[group]}
        if not all(math.isfinite(value) and value > 0 for value in overrides.values()):
            raise ValueError("derived diagnostic capacities must remain finite and positive")
        if overrides.get("vmax_VHK", resolved["vmax_VHK"]) > 5.0:
            raise ValueError("diagnostic would violate the HK ceiling")
        cases.append({"case_id": suffix, "stage": stage, "log_scales": scales, "parameter_overrides": overrides})
    for group in GROUPS:
        for step in (.05, .10):
            for sign in DIRECTIONS[group]:
                add({group: sign * step}, "single_group", f"{group}_{sign:+d}_h{step:.2f}")
    for first, second in itertools.combinations(GROUPS, 2):
        for signs in itertools.product(DIRECTIONS[first], DIRECTIONS[second]):
            add({first: signs[0] * .05, second: signs[1] * .05}, "paired_groups",
                f"{first}_{signs[0]:+d}__{second}_{signs[1]:+d}_h0.05")
    return {"protocol_type": "fixed_IC_coupled_energy_dynamic_sensitivity", "schema_version": 1,
            "status": "prepared_not_executed", "horizon_day": [1., 4.], "groups": GROUPS,
            "single_group_log_steps": [.05, .10], "paired_group_log_step": .05,
            "group_directions": DIRECTIONS, "parameter_caps": {"vmax_VHK": 5.0},
            "single_group_case_count": sum(c["stage"] == "single_group" for c in cases),
            "paired_group_case_count": sum(c["stage"] == "paired_groups" for c in cases),
            "planned_replays_with_strict_ultrastrict": len(cases) * 2, "cases": cases,
            "fixed_redox_initialization": "unchanged_baseline_NAD_1_NADH_1_mM",
            "initial_conditions_fitted": False, "parameter_trials_are_diagnostic_not_optimization": True,
            "optimization_allowed": False, "kinetic_promotion_allowed": False,
            "execution_requires_scientific_contract_complete": True,
            "sensitivities": {"investment": "one-sided log response [x(seed)-x(exp(-h))]/h; HK cannot increase",
                "AK_capacity": "central log response [x(exp(h))-x(exp(-h))]/(2h); both capacities scale together",
                "GAPDH_PGK_capacity": "central log response [x(exp(h))-x(exp(-h))]/(2h)",
                "paired_groups": "mixed finite differences, one-sided on investment and central on other groups; all required single-group terms retained"},
            "required_outputs": ["113 raw concentration trajectories", "ATP_ADP_AMP", "energy_charge", "NAD_NADH", "NADP_NADPH",
                "executed full ATP/ADP/AMP and purine balances", "executed VHK VPFK VAK VGAPDH VPGK VPK VDPGM VLDH",
                "native/effective rate distinction", "solver and quadrature residuals", "limiter participation",
                "all three separate endpoint errors, with biological pass unknown until readiness"],
            "rules": ["No observation resets, artificial ATP source or output clipping.",
                "Keep the frozen network, numerical threshold, redox ICs, purine controls and every unlisted parameter unchanged.",
                "HK/PFK scales are downward-only because HK is already at the 5.0 ceiling.",
                "Scaling AK forward and reverse capacities together does not establish thermodynamic correctness.",
                "Probe magnitudes are a finite-difference design, not biological parameter bounds or an optimizer search space.",
                "Keep response vectors and interactions separate: no best-case ranking or weighted-error promotion.",
                "Two probe sizes assess local response stability/nonlinearity, not biological uncertainty.",
                "This J1-J4 protocol cannot establish J1-J46 or external predictive validity."]}
