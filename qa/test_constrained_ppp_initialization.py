"""Tests for constrained latent PPP initial-state estimation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "diagnose_constrained_ppp_initialization.py"
SPEC = importlib.util.spec_from_file_location("diagnose_constrained_ppp_initialization", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
DIAG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIAG)


def test_latent_contract_contains_exactly_seven_unmeasured_pools() -> None:
    assert tuple(DIAG.LATENT_PPP_POOLS) == (
        "GL6P",
        "RU5P",
        "R5P",
        "X5P",
        "E4P",
        "S7P",
        "GA3P",
    )
    assert len(DIAG.LATENT_INDICES) == 7
    assert not set(DIAG.LATENT_INDICES) & set(DIAG.MEASURED_INDICES)


def test_state_override_locks_every_nonlatent_state() -> None:
    base = np.arange(114, dtype=float) + 1.0
    values = np.geomspace(1e-6, 1.0, 7)
    candidate = DIAG._state_with_latent(base, values)
    changed = set(np.flatnonzero(candidate != base).tolist())
    assert changed == set(DIAG.LATENT_INDICES.tolist())
    assert np.all(candidate[DIAG.MEASURED_INDICES] == base[DIAG.MEASURED_INDICES])


def test_residual_vector_has_expected_blocks() -> None:
    base = np.ones(114, dtype=float)
    residual = DIAG._residual_vector(
        log_values=np.log(np.full(7, 1e-3)),
        base_state=base,
        params={},
        teacher_initial=np.zeros(3),
        latent_scales=np.ones(7),
        teacher_scales=np.ones(3),
        latent_weight=1.0,
        teacher_weight=1.0,
        regularization_center=np.log(np.full(7, 1e-3)),
    )
    assert residual.shape == (17,)
    assert np.all(np.isfinite(residual))


def test_g6p_initial_teacher_is_insensitive_to_latent_states() -> None:
    state = np.ones(114, dtype=float)
    jacobian, rank = DIAG._teacher_sensitivity(state=state, params={})
    g6p_row = list(DIAG.MEASURED_PPP_POOLS).index("G6P")
    assert np.max(np.abs(jacobian[g6p_row])) < 1e-10
    assert rank <= 2


def test_seed_go6p_teacher_is_infeasible_even_at_saturating_gl6p() -> None:
    state = np.ones(114, dtype=float)
    state[int(DIAG.BRODBAR_METABOLITE_MAP["GO6P"])] = 0.12817966026893696
    feasibility = DIAG._go6p_fixed_kinetic_feasibility(
        state=state,
        params={},
        teacher_flux=-0.011398327305375912,
        bounded_gl6p_max=2.0,
    )
    assert feasibility["bounded_feasible"] is False
    assert feasibility["theoretically_feasible"] is False
    assert feasibility["dGO6P_at_GL6P_saturation"] < feasibility["teacher_dGO6P_initial"]
