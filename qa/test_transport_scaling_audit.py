"""Tests for compartment-volume and time-unit audit contracts."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_transport_scaling.py"
SPEC = importlib.util.spec_from_file_location("audit_transport_scaling", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_all_standard_transports_have_equal_legacy_coefficients() -> None:
    paired, unresolved = AUDIT._paired_transport_inventory()
    assert len(paired) >= 25
    assert all(row["current_concentration_derivative_ratio"] == 1.0 for row in paired)
    assert {row["reaction"] for row in unresolved} == {"VECYT"}


def test_hematocrit_scaling_contract() -> None:
    rows = AUDIT._scaling_rows({"VEGLC": {"mean_abs_flux": 0.3}})
    h60 = next(row for row in rows if row["hematocrit_fraction"] == 0.60)
    assert abs(h60["intracellular_to_extracellular_volume_ratio"] - 1.5) < 1e-12
    assert abs(h60["volume_corrected_intracellular_mean_abs_mM_per_day"] - 0.2) < 1e-12


def test_time_unit_conversion_is_not_proven_in_ode_history() -> None:
    evidence = AUDIT._time_unit_evidence()
    assert evidence["initial_source_contains_current_time_hours"] is True
    assert evidence["ode_source_changed_in_unit_label_commit"] is False
