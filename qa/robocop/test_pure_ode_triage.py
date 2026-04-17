"""Unit tests for services.robocop.pure_ode_triage."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_pure_ode_triage_module():
    """Load ``services/robocop/pure_ode_triage.py`` by absolute file path.

    Other tests in this suite (e.g. ``test_adapter_integration.py``) insert
    ``apps/api/`` on ``sys.path`` to mimic the FastAPI startup. That shadows
    the top-level ``services`` package, so a plain ``from services.robocop...``
    import fails when tests run together. Loading by file path is immune to
    the shadowing.
    """

    import importlib.util

    module_name = "robocop_pure_ode_triage_test_module"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    module_path = ROOT / "services" / "robocop" / "pure_ode_triage.py"
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Python 3.14 ``@dataclass`` looks up ``sys.modules[cls.__module__]``
    # while processing annotations; the module MUST be registered before
    # ``exec_module`` runs or every dataclass definition raises AttributeError.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_pure_ode_triage = _load_pure_ode_triage_module()

ADENYLATE_POOL_CRITICAL_RATIO = _pure_ode_triage.ADENYLATE_POOL_CRITICAL_RATIO
ADENYLATE_POOL_TARGET_RATIO = _pure_ode_triage.ADENYLATE_POOL_TARGET_RATIO
ATP_CONCERN_FLOOR = _pure_ode_triage.ATP_CONCERN_FLOOR
ATP_CRITICAL_FLOOR = _pure_ode_triage.ATP_CRITICAL_FLOOR
CombinedVerdict = _pure_ode_triage.CombinedVerdict
PureOdeVerdict = _pure_ode_triage.PureOdeVerdict
VERDICT_COLLAPSED = _pure_ode_triage.VERDICT_COLLAPSED
VERDICT_COMPROMISED = _pure_ode_triage.VERDICT_COMPROMISED
VERDICT_HEALTHY = _pure_ode_triage.VERDICT_HEALTHY
VERDICT_NEEDS_REVIEW = _pure_ode_triage.VERDICT_NEEDS_REVIEW
combine_triage_verdicts = _pure_ode_triage.combine_triage_verdicts
skipped_pure_ode_triage = _pure_ode_triage.skipped_pure_ode_triage
triage_pure_ode_csv = _pure_ode_triage.triage_pure_ode_csv
triage_pure_ode_trajectories = _pure_ode_triage.triage_pure_ode_trajectories


def _healthy_trajectories() -> Dict[str, List[float]]:
    """Trajectories that are physiologically healthy across the horizon.

    Every protected metabolite ends strictly above its concern floor so this
    fixture produces the ``healthy`` verdict on its own.
    """

    return {
        "ATP":   [1.60, 1.58, 1.55, 1.50, 1.45, 1.40],
        "ADP":   [0.20, 0.19, 0.18, 0.17, 0.16, 0.15],
        "AMP":   [0.09, 0.085, 0.08, 0.075, 0.072, 0.070],
        "IMP":   [0.05, 0.048, 0.045, 0.042, 0.040, 0.038],
        "EGLC":  [5.0, 4.7, 4.3, 3.8, 3.3, 2.8],
        "ELAC":  [0.10, 0.35, 0.70, 1.05, 1.40, 1.75],
        "LAC":   [1.0, 1.2, 1.4, 1.6, 1.8, 2.0],
        "PYR":   [0.05, 0.06, 0.07, 0.065, 0.06, 0.055],
        "PEP":   [0.01, 0.012, 0.013, 0.012, 0.011, 0.010],
        "B23PG": [4.8, 4.7, 4.6, 4.5, 4.4, 4.3],
        "GSH":   [2.1, 2.05, 2.0, 1.95, 1.9, 1.85],
        "GSSG":  [0.03, 0.032, 0.035, 0.038, 0.04, 0.042],
    }


def _trajectories_with_atp_concern_only() -> Dict[str, List[float]]:
    """ATP ends below the concern floor but the adenylate pool is safely small.

    ATP alone dropping to 0.20 while starting from a canonical pool (1.88)
    would force the pool ratio into ``critical``. That is the correct
    physiological reality — once ATP is concerning the pool usually is too.
    This fixture engineers a smaller starting pool (~0.6 mM) so the "ATP
    concern" case can be isolated from the adenylate-pool check in tests.
    """

    traj = _healthy_trajectories()
    traj["ATP"] = [0.35, 0.32, 0.28, 0.24, 0.22, 0.20]  # ends below concern 0.225
    traj["ADP"] = [0.20, 0.195, 0.19, 0.185, 0.18, 0.18]  # stays above concern
    traj["AMP"] = [0.09, 0.085, 0.08, 0.075, 0.072, 0.070]  # stays above concern
    return traj


def _times() -> List[float]:
    return [0.0, 8.4, 16.8, 25.2, 33.6, 42.0]


class TestHealthyPath:
    def test_healthy_trajectory_returns_healthy_verdict(self):
        verdict = triage_pure_ode_trajectories(_times(), _healthy_trajectories())
        assert verdict.overall == VERDICT_HEALTHY
        assert verdict.collapse_signals == []
        assert verdict.concern_signals == []
        assert verdict.healthy_signals, "expected at least one healthy signal"
        assert verdict.adenylate_pool is not None
        assert verdict.adenylate_pool.coherent is True
        assert verdict.adenylate_pool.state == "good"
        assert verdict.extracellular_anchor_status["EGLC"].state == "good"
        assert verdict.extracellular_anchor_status["ELAC"].state == "good"
        assert verdict.timepoint_count == 6
        assert verdict.horizon_days == pytest.approx(42.0)


class TestAbsoluteFloorViolations:
    def test_atp_collapse_triggers_collapsed_verdict(self):
        trajectories = _healthy_trajectories()
        # Make ATP collapse toward zero — the canonical fit-first failure mode
        # documented in AgentOps/Memory.md item 44.
        trajectories["ATP"] = [1.60, 1.20, 0.80, 0.40, 0.20, 0.05]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.overall == VERDICT_COLLAPSED
        assert any("ATP" in sig for sig in verdict.collapse_signals)
        assert verdict.protected_floor_status["ATP"].state == "critical"
        assert "Do not promote" in verdict.recommendation

    def test_adp_final_below_critical_is_collapsed(self):
        trajectories = _healthy_trajectories()
        trajectories["ADP"] = [0.20, 0.18, 0.15, 0.12, 0.08, 0.03]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.overall == VERDICT_COLLAPSED
        assert verdict.protected_floor_status["ADP"].state == "critical"

    def test_transient_collapse_is_still_critical(self):
        trajectories = _healthy_trajectories()
        # ATP dips below the critical floor transiently but recovers by the end.
        trajectories["ATP"] = [1.60, 0.10, 0.05, 1.20, 1.40, 1.50]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.protected_floor_status["ATP"].state == "critical"
        assert verdict.overall == VERDICT_COLLAPSED
        rationale = verdict.protected_floor_status["ATP"].rationale
        assert "below the critical" in rationale.lower()

    def test_concern_only_is_compromised_not_collapsed(self):
        # ATP ends at 0.20 (between critical 0.15 and concern 0.225) and the
        # adenylate pool starts small enough that it does not also crash.
        verdict = triage_pure_ode_trajectories(
            _times(), _trajectories_with_atp_concern_only()
        )
        assert verdict.overall == VERDICT_COMPROMISED
        assert verdict.protected_floor_status["ATP"].state == "concern"
        assert verdict.collapse_signals == []
        assert "Promote with caution" in verdict.recommendation

    def test_b23pg_critical_floor_triggers_collapse(self):
        trajectories = _healthy_trajectories()
        trajectories["B23PG"] = [4.8, 4.0, 3.0, 2.0, 1.5, 1.0]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.protected_floor_status["B23PG"].state == "critical"
        assert verdict.overall == VERDICT_COLLAPSED


class TestAdenylatePool:
    def test_pool_drift_below_target_is_concern(self):
        trajectories = _healthy_trajectories()
        # pool_start = 1.6+0.2+0.08 = 1.88; pool_end = 1.0+0.12+0.05 = 1.17
        # ratio = 1.17/1.88 = 0.62 < target 0.65 but > critical 0.40
        trajectories["ATP"] = [1.60, 1.50, 1.30, 1.15, 1.05, 1.00]
        trajectories["ADP"] = [0.20, 0.18, 0.16, 0.14, 0.13, 0.12]
        trajectories["AMP"] = [0.08, 0.075, 0.07, 0.06, 0.055, 0.05]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.adenylate_pool is not None
        assert verdict.adenylate_pool.state == "concern"
        assert verdict.adenylate_pool.coherent is False
        assert verdict.overall in {VERDICT_COMPROMISED, VERDICT_COLLAPSED}

    def test_pool_ratio_below_critical_is_collapse(self):
        trajectories = _healthy_trajectories()
        # ATP drops to 0.3 -> forces pool_ratio well below critical 0.40
        trajectories["ATP"] = [1.60, 1.20, 0.80, 0.50, 0.35, 0.30]
        trajectories["ADP"] = [0.20, 0.17, 0.14, 0.12, 0.10, 0.08]
        trajectories["AMP"] = [0.08, 0.07, 0.06, 0.055, 0.05, 0.05]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.adenylate_pool is not None
        assert verdict.adenylate_pool.state == "critical"
        assert verdict.overall == VERDICT_COLLAPSED
        assert any("Adenylate pool" in sig for sig in verdict.collapse_signals)

    def test_pool_is_missing_when_a_member_is_absent(self):
        trajectories = _healthy_trajectories()
        trajectories.pop("AMP")  # remove one pool member
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.adenylate_pool is not None
        assert verdict.adenylate_pool.state == "missing"
        assert verdict.adenylate_pool.coherent is False


class TestExtracellularAnchors:
    def test_eglc_rising_is_critical(self):
        trajectories = _healthy_trajectories()
        # EGLC rising over horizon is a structural wrong (transport broken).
        trajectories["EGLC"] = [5.0, 5.2, 5.4, 5.6, 5.8, 6.0]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.extracellular_anchor_status["EGLC"].state == "critical"
        assert verdict.overall == VERDICT_COLLAPSED

    def test_eglc_flat_is_concern(self):
        trajectories = _healthy_trajectories()
        trajectories["EGLC"] = [5.0, 5.0, 5.0, 5.0, 4.95, 4.9]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.extracellular_anchor_status["EGLC"].state == "concern"
        assert verdict.overall in {VERDICT_COMPROMISED, VERDICT_COLLAPSED}

    def test_elac_falling_is_critical(self):
        trajectories = _healthy_trajectories()
        trajectories["ELAC"] = [1.0, 0.9, 0.7, 0.5, 0.3, 0.2]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.extracellular_anchor_status["ELAC"].state == "critical"
        assert verdict.overall == VERDICT_COLLAPSED

    def test_elac_flat_is_concern(self):
        trajectories = _healthy_trajectories()
        trajectories["ELAC"] = [1.0, 1.01, 1.02, 1.02, 1.01, 1.01]
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.extracellular_anchor_status["ELAC"].state == "concern"


class TestMissingData:
    def test_empty_trajectories_returns_needs_review(self):
        verdict = triage_pure_ode_trajectories([], {})
        assert verdict.overall == VERDICT_NEEDS_REVIEW
        assert "No focus metabolites" in verdict.reason

    def test_partial_data_is_handled_gracefully(self):
        trajectories = {"ATP": [1.6, 1.4, 1.2], "ADP": [0.2, 0.18, 0.17]}
        verdict = triage_pure_ode_trajectories([0.0, 1.0, 2.0], trajectories)
        # With only ATP+ADP present, the adenylate pool cannot be computed.
        assert verdict.adenylate_pool is not None
        assert verdict.adenylate_pool.state == "missing"
        assert "AMP" in verdict.unavailable_metabolites
        assert any("not present" in c for c in verdict.caveats)

    def test_skipped_helper_returns_needs_review(self):
        verdict = skipped_pure_ode_triage("main.py did not finish")
        assert verdict.overall == VERDICT_NEEDS_REVIEW
        assert verdict.skipped is True
        assert verdict.skip_reason == "main.py did not finish"

    def test_case_insensitive_keys(self):
        trajectories = {k.lower(): v for k, v in _healthy_trajectories().items()}
        verdict = triage_pure_ode_trajectories(_times(), trajectories)
        assert verdict.overall == VERDICT_HEALTHY


class TestCsvEntryPoint:
    def test_csv_round_trip_produces_same_verdict(self, tmp_path: Path):
        # Write a small CSV with the same Brodbar main.py format.
        csv_path = tmp_path / "all_metabolites.csv"
        rows = _healthy_trajectories()
        times = _times()
        header = ["Time (days)"] + list(rows.keys())
        lines = [",".join(header)]
        for i, t in enumerate(times):
            line_values = [f"{t}"] + [f"{rows[name][i]}" for name in rows.keys()]
            lines.append(",".join(line_values))
        csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        verdict = triage_pure_ode_csv(csv_path)
        assert verdict.overall == VERDICT_HEALTHY
        assert verdict.csv_path and verdict.csv_path.endswith("all_metabolites.csv")
        assert verdict.timepoint_count == 6
        assert verdict.horizon_days == pytest.approx(42.0)

    def test_missing_csv_returns_skipped(self, tmp_path: Path):
        verdict = triage_pure_ode_csv(tmp_path / "nope.csv")
        assert verdict.overall == VERDICT_NEEDS_REVIEW
        assert verdict.skipped is True

    def test_none_path_returns_skipped(self):
        verdict = triage_pure_ode_csv(None)
        assert verdict.overall == VERDICT_NEEDS_REVIEW
        assert verdict.skipped is True

    def test_empty_csv_returns_skipped(self, tmp_path: Path):
        path = tmp_path / "empty.csv"
        path.write_text("Time (days),ATP\n", encoding="utf-8")
        verdict = triage_pure_ode_csv(path)
        assert verdict.overall == VERDICT_NEEDS_REVIEW
        assert verdict.skipped is True


class TestCombinedVerdict:
    def _calibration_keep(self) -> dict:
        return {
            "overall": "keep",
            "reason": "all good",
            "discard_triggers": [],
            "caveats": [],
            "next_best_experiment": "Promotion check recommended.",
        }

    def _calibration_discard(self) -> dict:
        return {
            "overall": "discard",
            "reason": "ATP worsened",
            "discard_triggers": ["ATP concern/critical"],
            "caveats": [],
            "next_best_experiment": "atp_focus rebalance",
        }

    def _calibration_caveats(self) -> dict:
        return {
            "overall": "keep_with_caveats",
            "reason": "mixed",
            "discard_triggers": [],
            "caveats": ["EGLC acceptable but GLC worse."],
            "next_best_experiment": None,
        }

    def test_pure_ode_collapse_overrides_calibration_keep(self):
        pure = triage_pure_ode_trajectories(
            _times(),
            {**_healthy_trajectories(), "ATP": [1.60, 1.20, 0.80, 0.40, 0.20, 0.05]},
        ).to_dict()
        combined = combine_triage_verdicts(self._calibration_keep(), pure)
        assert combined.overall == "discard"
        assert "Pure ODE collapsed" in combined.reason
        assert combined.discard_triggers, "expected pure-ODE collapse signals"

    def test_healthy_plus_calibration_keep_is_keep(self):
        pure = triage_pure_ode_trajectories(_times(), _healthy_trajectories()).to_dict()
        combined = combine_triage_verdicts(self._calibration_keep(), pure)
        assert combined.overall == "keep"
        assert "Next-best experiment" in combined.recommendation

    def test_pure_ode_compromise_with_keep_is_keep_with_caveats(self):
        pure = triage_pure_ode_trajectories(
            _times(), _trajectories_with_atp_concern_only()
        ).to_dict()
        assert pure["overall"] == VERDICT_COMPROMISED
        combined = combine_triage_verdicts(self._calibration_keep(), pure)
        assert combined.overall == "keep_with_caveats"
        assert combined.caveats

    def test_pure_ode_compromise_with_caveats_is_discard(self):
        pure = triage_pure_ode_trajectories(
            _times(), _trajectories_with_atp_concern_only()
        ).to_dict()
        assert pure["overall"] == VERDICT_COMPROMISED
        combined = combine_triage_verdicts(self._calibration_caveats(), pure)
        assert combined.overall == "discard"
        assert "too much accumulated risk" in combined.reason

    def test_calibration_discard_survives_healthy_ode(self):
        pure = triage_pure_ode_trajectories(_times(), _healthy_trajectories()).to_dict()
        combined = combine_triage_verdicts(self._calibration_discard(), pure)
        assert combined.overall == "discard"
        assert "Calibration-report triage returned discard" in combined.reason

    def test_keep_without_pure_ode_is_needs_review(self):
        combined = combine_triage_verdicts(self._calibration_keep(), None)
        assert combined.overall == "needs_review"
        assert "pure-ODE triage was not executed" in combined.reason

    def test_both_missing_is_needs_review(self):
        combined = combine_triage_verdicts(None, None)
        assert combined.overall == "needs_review"


class TestSerialisation:
    def test_to_dict_is_json_friendly(self):
        verdict = triage_pure_ode_trajectories(_times(), _healthy_trajectories())
        payload = verdict.to_dict()
        dumped = json.dumps(payload, default=str)
        assert '"overall"' in dumped
        assert '"protected_floor_status"' in dumped
        assert '"adenylate_pool"' in dumped
        assert '"extracellular_anchor_status"' in dumped

    def test_combined_to_dict_is_json_friendly(self):
        pure = triage_pure_ode_trajectories(_times(), _healthy_trajectories()).to_dict()
        calibration = {
            "overall": "keep",
            "reason": "ok",
            "discard_triggers": [],
            "caveats": [],
            "next_best_experiment": "Promote.",
        }
        combined = combine_triage_verdicts(calibration, pure)
        dumped = json.dumps(combined.to_dict(), default=str)
        assert '"calibration_triage"' in dumped
        assert '"pure_ode_triage"' in dumped
