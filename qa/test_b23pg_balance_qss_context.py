"""Tests for the exact B23PG balance audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_b23pg_balance_qss_context.py"
SPEC = importlib.util.spec_from_file_location("audit_b23pg_balance_qss_context", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_b23pg_balance_contract() -> None:
    assert AUDIT.B23PG_TERMS == {"VDPGM": 1.0, "V23DPGP": -1.0}
    fluxes = {"VDPGM": np.array([2.0, 3.0]), "V23DPGP": np.array([0.5, 1.0])}
    assert np.allclose(AUDIT._raw_balance(fluxes), [1.5, 2.0])


def test_state_contract_changes_only_b13pg_between_branches() -> None:
    states, params, _ = AUDIT._build_state_contract()
    revert = states[AUDIT.REVERT_LABEL]
    qss = states[AUDIT.QSS_LABEL]
    changed = set(np.flatnonzero(revert != qss).tolist())
    assert changed == {AUDIT.STATE_INDICES["B13PG"]}
    assert params["vmax_V6PGD"] == 9.0


def test_teacher_is_defined_on_audited_horizon() -> None:
    time, values, teacher = AUDIT._teacher()
    assert time[0] == 1.0
    assert time[-1] == 46.0
    assert np.isfinite(teacher([1.0, 3.0])).all()
    assert values[0] > values[-1]
