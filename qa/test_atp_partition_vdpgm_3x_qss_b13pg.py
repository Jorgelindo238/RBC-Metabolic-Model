"""Tests for the fixed-QSS VDPGM ATP partition audit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT = ROOT / "scripts" / "audit_atp_partition_vdpgm_3x_qss_b13pg.py"
SPEC = importlib.util.spec_from_file_location("atp_partition_vdpgm", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_contract_changes_only_vmax_vdpgm() -> None:
    state, seed, candidate, _ = AUDIT._build_contract()
    assert len(state) == 114
    assert AUDIT._changed_parameters(seed, candidate) == ["vmax_VDPGM"]
    assert candidate["vmax_VDPGM"] == 3.0 * seed["vmax_VDPGM"]


def test_windows_cover_early_transition_and_full_interval() -> None:
    assert AUDIT.WINDOWS[0] == ("J1_J1.1", 1.0, 1.1)
    assert AUDIT.WINDOWS[-1] == ("J1_J3", 1.0, 3.0)


def test_classifier_detects_vdpgm_diversion_at_fixed_supply() -> None:
    seed = {
        "VGAPDH_integral_J1_J3": 10.0,
        "VGAPDH_redox_drive_mean_J1_J3": 0.5,
        "VPGK_integral_J1_J3": 8.0,
        "VDPGM_integral_J1_J3": 2.0,
        "ATP_production_integral_J1_J3": 12.0,
        "ATP_consumption_integral_J1_J3": 11.0,
    }
    candidate = {
        "VGAPDH_integral_J1_J3": 10.1,
        "VGAPDH_redox_drive_mean_J1_J3": 0.505,
        "VPGK_integral_J1_J3": 7.0,
        "VDPGM_integral_J1_J3": 3.1,
        "ATP_production_integral_J1_J3": 11.0,
        "ATP_consumption_integral_J1_J3": 11.1,
    }
    result = AUDIT._classify(seed, candidate)
    assert result["classification"].startswith("VDPGM diversion")
    assert all(result["classification_gates"].values())
