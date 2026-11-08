"""Tests for fixed VAPRT suppression and residual VAMPD1 inference."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT = ROOT / "scripts" / "diagnose_vaprt_suppression_vampd1_requirement.py"
SPEC = importlib.util.spec_from_file_location("vaprt_zero", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_candidate_changes_only_vmax_vaprt() -> None:
    candidate, seed, changed = AUDIT._candidate_params(
        {"vmax_VAPRT": 4.0, "vmax_VAMPD1": 0.1}
    )
    assert seed == 4.0
    assert candidate["vmax_VAPRT"] == 0.0
    assert candidate["vmax_VAMPD1"] == 0.1
    assert changed == ["vmax_VAPRT"]


def test_required_vampd1_closes_total_balance() -> None:
    teacher = np.asarray([-0.1, 0.2])
    vak2 = np.asarray([0.2, 0.3])
    vsam = np.asarray([0.05, 0.1])
    vadsl = np.asarray([0.1, 0.2])
    vaprt = np.asarray([0.0, 0.0])
    required = AUDIT._required_vampd1(
        total_teacher_derivative=teacher,
        vak2=vak2,
        vsam=vsam,
        vadsl=vadsl,
        vaprt=vaprt,
    )
    np.testing.assert_allclose(vak2 - vsam + vadsl + vaprt - required, teacher)


def test_state_balance_contracts_match_purine_ownership() -> None:
    assert AUDIT.STATE_TERMS["ADE"] == {"VEADE": -1.0, "VAPRT": -1.0}
    assert AUDIT.STATE_TERMS["IMP"]["VAMPD1"] == 1.0
    assert AUDIT.STATE_TERMS["PRPP"]["VAPRT"] == -1.0
    assert AUDIT.STATE_TERMS["ADOMET"] == {"VSAM": 1.0, "VSAH": -1.0}


def test_classifier_rejects_vaprt_zero_when_ade_guard_fails() -> None:
    guards = {
        "ADE_noninferior_10pct": False,
        "adenylate_total_nrmse_improves": True,
        "required_VAMPD1_nonnegative": True,
        "required_VAMPD1_within_current_ceiling": True,
    }
    assert AUDIT._classify(guards) == "VAPRT_zero_rejected_by_ADE_teacher"


def test_observed_guard_contract_distinguishes_latent_states() -> None:
    assert AUDIT.OBSERVED_STATES == ("ATP", "ADP", "AMP", "IMP", "ADE")
    assert AUDIT.LATENT_GUARDS == ("PRPP", "ADOMET")
