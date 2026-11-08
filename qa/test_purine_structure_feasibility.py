"""Tests for the integrated purine structural-feasibility map."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_purine_structure_feasibility import structural_fluxes  # noqa: E402


def test_zero_aprt_corner_requires_eade_loss_and_minimum_amp_exit() -> None:
    row = structural_fluxes(
        aprt_integral=0.0,
        ade_loss=0.529,
        eade_loss=0.463,
        total_aprt_equivalent=-0.340,
    )
    assert row["VEADE_integral_mM"] == pytest.approx(0.529)
    assert row["EADE_loss_integral_mM"] == pytest.approx(0.992)
    assert row["AMP_NT_integral_mM"] == pytest.approx(0.340)


def test_no_eade_loss_corner_requires_aprt_and_larger_amp_exit() -> None:
    pair_loss = 0.529 + 0.463
    row = structural_fluxes(
        aprt_integral=pair_loss,
        ade_loss=0.529,
        eade_loss=0.463,
        total_aprt_equivalent=-0.340,
    )
    assert row["VEADE_integral_mM"] == pytest.approx(-0.463)
    assert row["EADE_loss_integral_mM"] == pytest.approx(0.0)
    assert row["AMP_NT_integral_mM"] == pytest.approx(1.332)


def test_every_continuum_point_closes_all_three_balances() -> None:
    ade_loss = 0.529
    eade_loss = 0.463
    total = -0.340
    for aprt in (0.0, 0.25, 0.75, ade_loss + eade_loss):
        row = structural_fluxes(
            aprt_integral=aprt,
            ade_loss=ade_loss,
            eade_loss=eade_loss,
            total_aprt_equivalent=total,
        )
        assert row["VEADE_integral_mM"] + row["APRT_integral_mM"] == pytest.approx(ade_loss)
        assert -row["VEADE_integral_mM"] + row["EADE_loss_integral_mM"] == pytest.approx(eade_loss)
        assert row["APRT_integral_mM"] - row["AMP_NT_integral_mM"] == pytest.approx(total)


def test_audit_contains_no_optimizer_or_ode_execution() -> None:
    source = (SCRIPTS / "audit_purine_structure_feasibility.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert "solve_ivp" not in source
    assert "custom_params" not in source
