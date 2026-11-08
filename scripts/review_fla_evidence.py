"""Re-audit network execution and cached FLA evidence without kinetic fitting."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.integrate import trapezoid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rbc_stoichiometry as stoich
from equadiff_brodbar import (
    BRODBAR_METABOLITE_MAP, MAX_DERIVATIVE, MODEL_NETWORK_VERSION,
    MIN_CONCENTRATION, NONEG_THRESHOLD, NUM_BASE_METABOLITES, PHI_INDEX, equadiff_brodbar,
)
from fla_multiple_shooting import duration_above_threshold


class SnapshotTracker:
    def __init__(self):
        self.fluxes = {}

    def add_timepoint(self, _time, fluxes):
        self.fluxes = dict(fluxes)


def audit_rhs(state, params=None):
    """Compare raw S v and floor-adjusted balances to the executed ODE."""
    tracker = SnapshotTracker()
    derivative = equadiff_brodbar(
        1.0, np.asarray(state, dtype=float).copy(), custom_params=params or {},
        curve_fit_strength=0.0, flux_tracker=tracker,
    )
    raw = np.zeros(NUM_BASE_METABOLITES)
    missing = sorted(set(stoich.STOICHIOMETRY) - set(tracker.fluxes))
    if missing:
        raise RuntimeError(f"Stoichiometric reactions absent from tracker: {missing}")
    for reaction, coefficients in stoich.STOICHIOMETRY.items():
        for name, coefficient in coefficients.items():
            index = BRODBAR_METABOLITE_MAP[name]
            if index < NUM_BASE_METABOLITES:
                raw[index] += coefficient * tracker.fluxes[reaction]
    effective = raw.copy()
    concentration = np.maximum(np.asarray(state[:NUM_BASE_METABOLITES]), MIN_CONCENTRATION)
    mask = (concentration < NONEG_THRESHOLD) & (effective < 0.0)
    effective[mask] *= concentration[mask] / NONEG_THRESHOLD
    effective = np.clip(effective, -MAX_DERIVATIVE, MAX_DERIVATIVE)
    executed = np.asarray(derivative[:NUM_BASE_METABOLITES])
    difference = executed - raw
    inverse = {index: name for name, index in BRODBAR_METABOLITE_MAP.items()}
    return {
        "max_effective_balance_error_mM_per_day": float(np.max(np.abs(executed - effective))),
        "max_raw_stoichiometric_defect_mM_per_day": float(np.max(np.abs(difference))),
        "raw_balance_defect_by_state": {
            inverse[index]: float(difference[index])
            for index in np.flatnonzero(np.abs(difference) > 1e-10)
        },
        "tracked_flux_count": len(tracker.fluxes),
    }


def run():
    out = ROOT / "output" / "fla_review_2026_09_08"
    source = ROOT / "output" / "brodbar_multiple_shooting_diagnostic"
    previous = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    free_path = Path(previous["source_free_run"])
    reset_path = source / "multiple_shooting_timeseries.csv"
    free = pd.read_csv(free_path)
    free = free.loc[free["candidate"] == "VAMPD1_storage_decay"]
    reset = pd.read_csv(reset_path)
    horizon = float(free.time_day.iloc[-1] - free.time_day.iloc[0])
    segment_duration = sum(
        float(frame.time_day.iloc[-1] - frame.time_day.iloc[0])
        for _, frame in reset.groupby("segment")
    )
    if not np.isclose(horizon, segment_duration):
        raise ValueError("free and segmented trajectories must cover equal durations")
    corrected = {
        "threshold_mM": 0.01,
        "free_run": duration_above_threshold(free.time_day, free.ATP, threshold=0.01) / horizon,
        "observation_reset": sum(
            duration_above_threshold(frame.time_day, frame.ATP, threshold=0.01)
            for _, frame in reset.groupby("segment")
        ) / segment_duration,
        "method": "piecewise_linear_elapsed_duration_excluding_reset_jumps",
        "is_sensitivity_or_validation_evidence": False,
    }
    raw_adenylate_rate = (
        free.VAK2 - free.VSAM + free.VADSL + free.VAPRT - free.VAMPD1 - free.VAMP_NT
    )
    adenylate_defect = free.dadenylate_total_ode_dt - raw_adenylate_rate
    rng = np.random.default_rng(20260908)
    audits = {}
    for index in range(8):
        state = rng.uniform(0.01, 2.0, NUM_BASE_METABOLITES + 1)
        state[PHI_INDEX] = 7.2
        audits[f"positive_state_{index}"] = audit_rhs(state)
    state = np.full(NUM_BASE_METABOLITES + 1, 0.2)
    state[PHI_INDEX] = 7.2
    for name in ("ATP", "GTP", "G6P", "B13PG"):
        state[BRODBAR_METABOLITE_MAP[name]] = 1e-6
    audits["depleted_pools"] = audit_rhs(state)
    state[BRODBAR_METABOLITE_MAP["ATP"]] = 0.0
    state[BRODBAR_METABOLITE_MAP["ADP"]] = 0.0
    params = {name: 0.0 for name in stoich.KNOWN_PARAM_UNIVERSE if name.startswith("vmax_")}
    params.update({"vmax_VAK_rev": 1.0})
    audits["isolated_reverse_AK_at_zero_ATP_ADP"] = audit_rhs(state, params)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "network_version": MODEL_NETWORK_VERSION,
        "stoichiometry_schema_version": stoich.STOICHIOMETRY_SCHEMA_VERSION,
        "optimization_performed": False,
        "parameters_promoted": False,
        "agent_reviews_completed": 0,
        "review_execution": "local_after_three_agent_quota_failures",
        "inventory": {
            "concentration_states": NUM_BASE_METABOLITES,
            "default_states_including_pHi": NUM_BASE_METABOLITES + 1,
            "declared_reactions_or_rates": len(stoich.ALL_REACTIONS),
            "stoichiometric_reactions": len(stoich.STOICHIOMETRY),
            "parameters_in_nonhybrid_structural_scope": len(stoich.ALL_PARAMETERS),
            "known_parameter_keys_including_switches": len(stoich.KNOWN_PARAM_UNIVERSE),
        },
        "rhs_audits": audits,
        "ATP_elapsed_time_fraction_corrected": corrected,
        "cached_adenylate_raw_balance_audit": {
            "max_absolute_defect_mM_per_day": float(np.max(np.abs(adenylate_defect))),
            "signed_defect_integral_mM": float(trapezoid(adenylate_defect, free.time_day)),
            "absolute_defect_integral_mM": float(trapezoid(np.abs(adenylate_defect), free.time_day)),
            "definition": "recorded d(ATP+ADP+AMP)/dt minus (VAK2-VSAM+VADSL+VAPRT-VAMPD1-VAMP_NT)",
            "scope": "cached sampled replay, not pre-clipping solver states; integrals use trapezoid quadrature",
        },
        "superseded_sample_fraction": previous.get("ATP_informative_time_fraction"),
        "continuity_loss_reported_not_optimized": previous["mean_normalized_continuity_jump_loss"],
        "input_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (free_path, reset_path, source / "summary.json",
                         ROOT / "src" / "equadiff_brodbar.py", ROOT / "src" / "rbc_stoichiometry.py")
        },
        "limitations": [
            "RHS equality is implementation consistency, not elemental or thermodynamic validation.",
            "State availability is not kinetic identifiability; no sensitivities were measured here.",
            "Cached trajectories were not rerun and do not recover pre-clipping minima.",
            "Observation-reset errors are not held-out continuous prediction scores.",
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidence.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
    return result


if __name__ == "__main__":
    run()
