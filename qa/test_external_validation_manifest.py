"""Tests for conservative external validation target provenance."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_external_validation_manifest import classify_series  # noqa: E402


def test_constant_one_bardyn_rows_are_excluded() -> None:
    assert classify_series([1.0, 1.0, 1.0], placeholder_policy=True) == (
        "excluded_constant_one_placeholder"
    )
    assert classify_series([1.0, 0.9, 0.8], placeholder_policy=True) == "observed"


def test_constant_one_is_not_automatically_excluded_without_placeholder_policy() -> None:
    assert classify_series([1.0, 1.0], placeholder_policy=False) == "observed"


def test_manifest_does_not_fit_external_data() -> None:
    source = (SCRIPTS / "build_external_validation_manifest.py").read_text(
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
