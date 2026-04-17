from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "services" / "robocop" / "calibration_triage_env.py"


def _load_env_module():
    module_name = "qa_calibration_triage_env"
    spec = importlib.util.spec_from_file_location(module_name, str(MODULE_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load calibration_triage_env from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


env_module = _load_env_module()
CalibrationTriageEnv = env_module.CalibrationTriageEnv
preferred_action = env_module.preferred_action


def test_preferred_action_promotes_strong_keep():
    record = {
        "combined_triage": {"overall": "keep"},
        "improvement_pct": 8.5,
    }
    assert preferred_action(record) == "promote"


def test_preferred_action_discards_collapsed_pure_ode():
    record = {
        "pure_ode_triage": {"overall": "collapsed"},
        "improvement_pct": 25.0,
    }
    assert preferred_action(record) == "discard"


def test_calibration_triage_env_steps_and_accumulates_reward():
    env = CalibrationTriageEnv(
        [
            {"combined_triage": {"overall": "keep"}, "improvement_pct": 7.0},
            {"combined_triage": {"overall": "discard"}, "improvement_pct": 2.0},
        ]
    )

    observation = env.reset()
    assert observation["combined_overall"] == "keep"

    step_one = env.step("promote")
    assert step_one.reward == 1.0
    assert step_one.terminated is False
    assert step_one.info["target_action"] == "promote"

    step_two = env.step("discard")
    assert step_two.reward == 1.0
    assert step_two.terminated is True
