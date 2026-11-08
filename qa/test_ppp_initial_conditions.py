"""Tests for the controlled latent PPP initial-condition replay."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "diagnose_ppp_initial_conditions.py"
SPEC = importlib.util.spec_from_file_location("diagnose_ppp_initial_conditions", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
DIAGNOSTIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIAGNOSTIC)


def test_historical_state_changes_only_latent_ppp_pools() -> None:
    current = np.ones(115, dtype=float)
    historical = {pool: 0.01 * (index + 1) for index, pool in enumerate(DIAGNOSTIC.LATENT_PPP_POOLS)}
    corrected, changes = DIAGNOSTIC._historical_latent_ppp_state(current, historical)
    changed = set(np.flatnonzero(np.abs(corrected - current) > 1e-15).tolist())
    expected = {DIAGNOSTIC.BRODBAR_METABOLITE_MAP[pool] for pool in DIAGNOSTIC.LATENT_PPP_POOLS}
    assert changed == expected
    assert {row["pool"] for row in changes} == set(DIAGNOSTIC.LATENT_PPP_POOLS)


def test_measured_ppp_initial_states_are_preserved() -> None:
    current = np.arange(115, dtype=float) + 0.5
    historical = {pool: 0.01 for pool in DIAGNOSTIC.LATENT_PPP_POOLS}
    corrected, _ = DIAGNOSTIC._historical_latent_ppp_state(current, historical)
    for pool in DIAGNOSTIC.MEASURED_PPP_POOLS:
        index = DIAGNOSTIC.BRODBAR_METABOLITE_MAP[pool]
        assert corrected[index] == current[index]


def test_decision_advances_guarded_ppp_improvement() -> None:
    rows = []
    for case, scale in ((DIAGNOSTIC.CASE_CURRENT, 1.0), (DIAGNOSTIC.CASE_HISTORICAL, 0.8)):
        for pool in DIAGNOSTIC.MEASURED_PPP_POOLS:
            rows.append(
                {
                    "candidate": case,
                    "pool": pool,
                    "concentration_nrmse": 10.0 * scale,
                    "net_teacher_nrmse": 5.0 * scale,
                }
            )
    decision, _, _ = DIAGNOSTIC._decision(rows, [])
    assert "candidate baseline" in decision


def test_decision_rejects_guard_failure() -> None:
    rows = []
    for case, scale in ((DIAGNOSTIC.CASE_CURRENT, 1.0), (DIAGNOSTIC.CASE_HISTORICAL, 0.5)):
        for pool in DIAGNOSTIC.MEASURED_PPP_POOLS:
            rows.append(
                {
                    "candidate": case,
                    "pool": pool,
                    "concentration_nrmse": 10.0 * scale,
                    "net_teacher_nrmse": 5.0 * scale,
                }
            )
    decision, _, _ = DIAGNOSTIC._decision(rows, ["ATP guard"])
    assert decision.startswith("reject")


def test_decision_routes_go6p_transfer_to_v6pgd_screen() -> None:
    rows = []
    values = {
        DIAGNOSTIC.CASE_CURRENT: {
            "G6P": (10.0, 10.0),
            "GO6P": (1.0, 2.0),
            "F6P": (20.0, 50.0),
        },
        DIAGNOSTIC.CASE_HISTORICAL: {
            "G6P": (12.0, 11.0),
            "GO6P": (1.0, 15.0),
            "F6P": (15.0, 15.0),
        },
    }
    for candidate, pools in values.items():
        for pool, (concentration, teacher) in pools.items():
            rows.append(
                {
                    "candidate": candidate,
                    "pool": pool,
                    "concentration_nrmse": concentration,
                    "net_teacher_nrmse": teacher,
                }
            )
    decision, _, _ = DIAGNOSTIC._decision(rows, ["ATP guard"])
    assert "vmax_V6PGD" in decision
