from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from screen_vmax_vampd1_vaprt_zero import (  # noqa: E402
    MULTIPLIERS,
    _candidate_params,
    _guards,
    _label,
)


def _metric_payload(
    *,
    total: float = 1.0,
    slope: float = 1.0,
    endpoint: float = 1.0,
    amp: float = 1.0,
    flux: float = 1.0,
    forward: float = 1.0,
) -> dict:
    states = {
        state: {"nrmse": 1.0}
        for state in ("ATP", "ADP", "AMP", "IMP", "ADE")
    }
    states["AMP"]["nrmse"] = amp
    states["adenylate_total"] = {
        "nrmse": total,
        "slope_nrmse": slope,
        "endpoint_error": endpoint,
    }
    states["VAMPD1_flux"] = {"nrmse": flux}
    states["PRPP"] = {"minimum_mM": 0.1, "max_abs_excursion_mM": 0.5}
    states["ADOMET"] = {"minimum_mM": 0.1, "max_abs_excursion_mM": 0.5}
    states["VAK_directionality"] = {"forward_time_fraction": forward}
    states["whole_panel"] = {"mean_nrmse": 1.0, "median_nrmse": 1.0}
    return {
        "state_metrics": states,
        "closures": {
            "max_abs_total_adenylate_closure_error": 1e-12,
            "all_state_minimum_mM": 1e-6,
        },
    }


def test_multiplier_grid_matches_registered_contract() -> None:
    assert MULTIPLIERS == (1.0, 1.1, 1.2, 1.25, 1.3, 1.4, 1.5)


def test_candidate_contract_changes_only_vampd1_after_vaprt_suppression() -> None:
    fixed = {"vmax_VAPRT": 4.0, "vmax_VAMPD1": 0.08, "other": 2.0}
    baseline, seed, changed_seed, changed_fixed = _candidate_params(fixed, 1.0)
    assert baseline["vmax_VAPRT"] == 0.0
    assert baseline["vmax_VAMPD1"] == seed == 0.08
    assert changed_seed == []
    assert changed_fixed == ["vmax_VAPRT"]
    candidate, _, changed_seed, changed_fixed = _candidate_params(fixed, 1.25)
    assert np.isclose(candidate["vmax_VAMPD1"], 0.1)
    assert changed_seed == ["vmax_VAMPD1"]
    assert changed_fixed == ["vmax_VAMPD1", "vmax_VAPRT"]


def test_guards_require_all_predeclared_target_improvements() -> None:
    baseline = _metric_payload()
    candidate = _metric_payload(
        total=0.8, slope=0.8, endpoint=0.8, amp=0.8, flux=0.8
    )
    guards = _guards(
        candidate=candidate,
        baseline=baseline,
        closure_tolerance=1e-7,
        include_whole_panel=True,
    )
    assert all(guards.values())
    candidate["state_metrics"]["adenylate_total"]["slope_nrmse"] = 1.01
    guards = _guards(
        candidate=candidate,
        baseline=baseline,
        closure_tolerance=1e-7,
        include_whole_panel=False,
    )
    assert not guards["adenylate_total_slope_improves"]


def test_vak_and_latent_guards_are_active() -> None:
    baseline = _metric_payload()
    candidate = _metric_payload(
        total=0.8,
        slope=0.8,
        endpoint=0.8,
        amp=0.8,
        flux=0.8,
        forward=0.98,
    )
    candidate["state_metrics"]["PRPP"]["max_abs_excursion_mM"] = 0.7
    guards = _guards(
        candidate=candidate,
        baseline=baseline,
        closure_tolerance=1e-7,
        include_whole_panel=False,
    )
    assert not guards["VAK_directionality_preserved"]
    assert not guards["PRPP_preserved"]


def test_runner_contains_no_adaptive_optimization() -> None:
    source_path = SCRIPTS / "screen_vmax_vampd1_vaprt_zero.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert "study" not in source.lower()
    assert _label(1.25) == "vmax_VAMPD1_1.250x"
