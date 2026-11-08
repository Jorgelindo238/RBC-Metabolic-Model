"""Tests for the fixed-state VADSS saturation audit."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_vadss_saturation_vampd1_decay import (  # noqa: E402
    _sensitivity_diagnostics,
    build_joint_vadss_targets,
    michaelis_fraction,
    reweighted_vadss_flux,
)


def test_vadss_flux_is_product_of_three_saturation_factors() -> None:
    flux = reweighted_vadss_flux(
        imp=[0.1],
        asp=[0.2],
        gtp=[0.5],
        vmax=2.0,
        km_imp=0.1,
        km_asp=0.2,
        km_gtp=0.5,
    )
    np.testing.assert_allclose(flux, [0.25])


def test_invalid_michaelis_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        michaelis_fraction([0.1], 0.0)
    with pytest.raises(ValueError):
        michaelis_fraction([-0.1], 0.2)


def test_joint_teacher_uses_adenylate_required_vampd1_not_model_vampd1() -> None:
    import pandas as pd

    frame = pd.DataFrame(
        {
            "time_day": [1.0, 2.0],
            "VAK2": [0.0, 0.0],
            "VSAM": [0.0, 0.0],
            "VADSL": [0.0, 0.0],
            "VAPRT": [0.0, 0.0],
            "VAMPD1": [99.0, 99.0],
            "VHGPRT1": [0.0, 0.0],
            "VIMPH": [0.0, 0.0],
            "Vnucleo2": [0.0, 0.0],
        }
    )
    curves = {
        "ATP": np.asarray([1.0, 0.8]),
        "ADP": np.asarray([1.0, 1.0]),
        "AMP": np.asarray([1.0, 1.0]),
        "IMP": np.asarray([0.1, 0.2]),
    }
    import audit_vadss_saturation_vampd1_decay as audit

    original_windows = audit.WINDOWS
    audit.WINDOWS = ((1.0, 2.0),)
    try:
        targets = build_joint_vadss_targets(
            frame,
            np.asarray([1.0, 2.0]),
            curves,
            np.asarray([0.1, 0.1]),
        )
    finally:
        audit.WINDOWS = original_windows
    assert targets[0].required_unknown_flux_integral_mM == pytest.approx(0.1)


def test_vmax_and_km_gtp_are_locally_identifiable_across_windows() -> None:
    time = np.linspace(1.0, 46.0, 451)
    diagnostics = _sensitivity_diagnostics(
        time=time,
        imp=np.linspace(0.12, 0.01, time.size),
        asp=np.linspace(0.18, 3.0, time.size),
        gtp=np.geomspace(1.0, 0.002, time.size),
        vmax=1.5,
        substrate="GTP",
        km=0.2,
    )
    assert diagnostics["rank"] == 2
    assert diagnostics["identifiable"] is True


def test_audit_does_not_run_an_optimizer_or_the_ode() -> None:
    source = (SCRIPTS / "audit_vadss_saturation_vampd1_decay.py").read_text(
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
