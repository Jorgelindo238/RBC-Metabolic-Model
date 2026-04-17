from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "services" / "robocop" / "calibration_phase_b.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_phase_b_module():
    module_name = "qa_phase_b_pure_ode_gate"
    spec = importlib.util.spec_from_file_location(module_name, str(MODULE_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load calibration_phase_b from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


phase_b = _load_phase_b_module()


def test_classify_decision_discards_when_candidate_pure_ode_collapses():
    decision, reason = phase_b._classify_decision(
        fit_summary={
            "meaningful_improvement": True,
            "protected_fit_status": {},
        },
        pure_ode_delta={
            "ATP": {"status": "better"},
            "ADP": {"status": "better"},
            "EGLC": {"status": "better"},
        },
        protected_metabolites=["ATP", "ADP", "EGLC", "ELAC", "LAC"],
        candidate_pure_ode_triage={
            "overall": "collapsed",
            "reason": "ATP crossed a protected floor.",
        },
    )

    assert decision == "discard"
    assert "collapsed" in reason.lower()
