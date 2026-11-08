"""Static tests for the Brodbar multiple-shooting diagnostic."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_diagnostic_is_not_an_optimizer_and_disables_curve_forcing() -> None:
    source = (SCRIPTS / "diagnose_brodbar_multiple_shooting.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert '"curve_fit_forcing_inside_segments": False' in source


def test_ambiguous_b13pg_and_grouped_pg_signal_are_not_reset() -> None:
    source = (SCRIPTS / "diagnose_brodbar_multiple_shooting.py").read_text(
        encoding="utf-8"
    )
    assert 'EXCLUDED_RESETS = {"B13PG", "P2G", "P3G"}' in source
