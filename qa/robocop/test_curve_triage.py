"""Unit tests for services.robocop.curve_triage."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.robocop.curve_triage import (  # noqa: E402
    skipped_triage,
    triage_calibration_report,
)


def _entry(name: str, nrmse: float, **extra) -> Dict[str, Any]:
    base = {
        "name": name,
        "nrmse": nrmse,
        "rmse": extra.get("rmse", nrmse * 0.1),
        "sim_final": extra.get("sim_final", 1.0),
        "exp_final": extra.get("exp_final", 1.0),
        "norm_factor": extra.get("norm_factor", 0.1),
    }
    base.update(extra)
    return base


def _report(per_metabolite: List[Dict[str, Any]], *, baseline: float = 1.0, final: float = 0.5) -> Dict[str, Any]:
    return {
        "baseline_loss": baseline,
        "final_loss": final,
        "improvement_pct": (1 - final / baseline) * 100,
        "per_metabolite": per_metabolite,
    }


class TestHappyPath:
    def test_all_priority_1_good_yields_keep(self):
        report = _report([
            _entry("EGLC", 0.10),
            _entry("GLC", 0.15),
            _entry("ELAC", 0.10),
            _entry("LAC", 0.20),
            _entry("ATP", 0.12),
            _entry("ADP", 0.12),
            _entry("AMP", 0.22),
            _entry("B23PG", 0.18),
            _entry("GSH", 0.20),
            _entry("GSSG", 0.20),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=[
                "EGLC", "GLC", "ELAC", "LAC",
                "ATP", "ADP", "AMP",
                "B23PG", "GSH", "GSSG",
            ],
            optimized_params=["vmax_VHK", "vmax_VEGLC"],
        )
        assert verdict.overall == "keep"
        assert verdict.discard_triggers == []
        assert verdict.keep_signals, "expected at least one keep signal"
        assert verdict.protected_metric_status.adenylate_coherent is True

    def test_priority_1_mixed_but_no_criticals_yields_caveats(self):
        report = _report([
            _entry("EGLC", 0.4),
            _entry("ELAC", 0.4),
            _entry("ATP", 0.4),
            _entry("ADP", 0.4),
            _entry("AMP", 0.4),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=["EGLC", "ELAC", "ATP", "ADP", "AMP"],
        )
        assert verdict.overall == "keep_with_caveats"


class TestDiscardPaths:
    def test_atp_collapse_triggers_discard(self):
        report = _report([
            _entry("EGLC", 0.15),
            _entry("ATP", 1.5),
            _entry("ADP", 0.3),
            _entry("AMP", 0.3),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
        )
        assert verdict.overall == "discard"
        assert any("ATP" in trigger for trigger in verdict.discard_triggers)
        assert verdict.next_best_experiment and "atp_focus" in verdict.next_best_experiment.lower()

    def test_purine_win_with_energy_regression_is_discard(self):
        report = _report([
            _entry("ATP", 0.6),  # concern
            _entry("ADP", 0.3),
            _entry("AMP", 0.3),
            _entry("IMP", 0.15),  # purine good
            _entry("HYPX", 0.2),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=["ATP", "ADP", "AMP", "IMP", "HYPX"],
        )
        assert verdict.overall == "discard"
        assert any("Purine" in trig for trig in verdict.discard_triggers)

    def test_side_metabolism_win_with_energy_regression_is_discard(self):
        report = _report([
            _entry("ATP", 0.7),
            _entry("SER", 0.10),
            _entry("MAL", 0.15),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=["ATP", "SER", "MAL"],
        )
        assert verdict.overall == "discard"
        assert any("Priority 4" in trig for trig in verdict.discard_triggers)

    def test_priority_1_critical_alone_triggers_discard(self):
        report = _report([
            _entry("EGLC", 1.4),  # critical
            _entry("ELAC", 0.2),
            _entry("ATP", 0.2),
            _entry("ADP", 0.2),
            _entry("AMP", 0.2),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=["EGLC", "ELAC", "ATP", "ADP", "AMP"],
        )
        assert verdict.overall == "discard"
        assert any("EGLC" in trig for trig in verdict.discard_triggers)


class TestCaveats:
    def test_extracellular_ok_intracellular_off_raises_caveat(self):
        report = _report([
            _entry("EGLC", 0.2),  # acceptable extracellular
            _entry("GLC", 0.9),   # concern intracellular
            _entry("ATP", 0.2),
            _entry("ADP", 0.2),
            _entry("AMP", 0.2),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=["EGLC", "GLC", "ATP", "ADP", "AMP"],
        )
        assert verdict.overall in {"keep_with_caveats", "discard"}
        assert any("EGLC" in c for c in verdict.caveats)

    def test_dangerous_compensator_active_caveat(self):
        report = _report([
            _entry("EGLC", 0.15),
            _entry("ELAC", 0.15),
            _entry("ATP", 0.15),
            _entry("ADP", 0.15),
            _entry("AMP", 0.15),
            _entry("GLC", 0.15),
            _entry("LAC", 0.15),
            _entry("B23PG", 0.15),
            _entry("GSH", 0.15),
            _entry("GSSG", 0.15),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=[
                "EGLC", "ELAC", "ATP", "ADP", "AMP", "GLC", "LAC", "B23PG", "GSH", "GSSG",
            ],
            optimized_params=["vmax_VPEP_PASE", "vmax_VHK"],
        )
        assert "vmax_VPEP_PASE" in verdict.dangerous_compensators_active
        # With all P1 good and a compensator active, the verdict should
        # warn but not discard outright.
        assert verdict.overall in {"keep", "keep_with_caveats"}
        assert any("compensator" in c.lower() for c in verdict.caveats)

    def test_adenylate_spread_warning(self):
        report = _report([
            _entry("EGLC", 0.20),
            _entry("ELAC", 0.20),
            _entry("ATP", 0.05),
            _entry("ADP", 0.75),
            _entry("AMP", 0.75),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=["EGLC", "ELAC", "ATP", "ADP", "AMP"],
        )
        # Concern-level ADP/AMP with healthy ATP should surface a caveat and
        # mark the pool as incoherent, but not force a hard discard.
        assert verdict.protected_metric_status.adenylate_coherent is False
        assert any("incoherent" in c.lower() for c in verdict.caveats)

    def test_adenylate_collapse_triggers_discard(self):
        report = _report([
            _entry("EGLC", 0.20),
            _entry("ELAC", 0.20),
            _entry("ATP", 0.05),
            _entry("ADP", 1.3),
            _entry("AMP", 1.2),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=["EGLC", "ELAC", "ATP", "ADP", "AMP"],
        )
        # Critical ADP/AMP with healthy ATP is nonphysical and must discard.
        assert verdict.overall == "discard"
        assert any("collapsed" in trig for trig in verdict.discard_triggers)


class TestMissingOrIncompleteReports:
    def test_missing_per_metabolite_block_returns_needs_review(self):
        verdict = triage_calibration_report({"baseline_loss": 1.0, "final_loss": 0.5})
        assert verdict.overall == "needs_review"
        assert verdict.per_metabolite == []

    def test_measured_but_missing_from_report_is_surfaced(self):
        report = _report([
            _entry("ATP", 0.2),
            _entry("ADP", 0.2),
            _entry("AMP", 0.2),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=["ATP", "ADP", "AMP", "EGLC"],
        )
        assert verdict.measured_but_missing_from_report == ["EGLC"]

    def test_unrecognised_metabolite_still_gets_priority_0(self):
        report = _report([_entry("MYSTERY", 0.2)])
        verdict = triage_calibration_report(report)
        assert verdict.per_metabolite[0].priority == 0
        assert verdict.per_metabolite[0].category == "uncategorised"

    def test_skipped_triage_helper_returns_needs_review(self):
        verdict = skipped_triage("calibration did not finish")
        assert verdict.overall == "needs_review"
        assert verdict.skipped is True
        assert verdict.skip_reason == "calibration did not finish"


class TestNextBestExperiment:
    def test_suggests_purine_stage_when_only_p3_outstanding(self):
        report = _report([
            _entry("EGLC", 0.15),
            _entry("GLC", 0.15),
            _entry("ELAC", 0.15),
            _entry("LAC", 0.15),
            _entry("ATP", 0.15),
            _entry("ADP", 0.15),
            _entry("AMP", 0.15),
            _entry("B23PG", 0.15),
            _entry("GSH", 0.15),
            _entry("GSSG", 0.15),
            _entry("G6P", 0.2),
            _entry("PEP", 0.2),
            _entry("PYR", 0.2),
            _entry("IMP", 1.6),  # purine concern/critical (1.6 > 1.5)
            _entry("HYPX", 1.6),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=[
                "EGLC", "GLC", "ELAC", "LAC", "ATP", "ADP", "AMP", "B23PG",
                "GSH", "GSSG", "G6P", "PEP", "PYR", "IMP", "HYPX",
            ],
        )
        assert verdict.next_best_experiment and "core_km_then_purine_transport" in verdict.next_best_experiment

    def test_promotion_suggestion_when_everything_green(self):
        report = _report([
            _entry("EGLC", 0.10),
            _entry("ELAC", 0.10),
            _entry("ATP", 0.10),
            _entry("ADP", 0.10),
            _entry("AMP", 0.10),
            _entry("GLC", 0.10),
            _entry("LAC", 0.10),
            _entry("B23PG", 0.10),
            _entry("GSH", 0.10),
            _entry("GSSG", 0.10),
        ])
        verdict = triage_calibration_report(
            report,
            measured_metabolites=[
                "EGLC", "ELAC", "ATP", "ADP", "AMP", "GLC", "LAC", "B23PG", "GSH", "GSSG",
            ],
        )
        assert verdict.overall == "keep"
        assert verdict.next_best_experiment and "promotion" in verdict.next_best_experiment.lower()


class TestSerialisation:
    def test_to_dict_is_json_friendly(self):
        import json
        report = _report([_entry("ATP", 0.2), _entry("ADP", 0.2), _entry("AMP", 0.2)])
        verdict = triage_calibration_report(report, measured_metabolites=["ATP", "ADP", "AMP"])
        payload = verdict.to_dict()
        dumped = json.dumps(payload, default=str)
        assert '"overall"' in dumped
        assert '"per_metabolite"' in dumped
        assert '"protected_metric_status"' in dumped
