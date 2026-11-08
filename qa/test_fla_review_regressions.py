"""Behavioral regression tests from the September FLA review."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from fla_integrated_flux import build_integrated_flux_targets
from fla_multiple_shooting import duration_above_threshold, forward_chaining_splits, reset_observed_states


@pytest.mark.parametrize("field", ["measurement_values", "known_rate", "model_unknown_rate"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_integrated_teachers_reject_missing_or_nonfinite_samples(field, bad):
    kwargs = dict(
        measurement_time=[1.0, 2.0], measurement_values=[1.0, 0.5],
        dense_time=[1.0, 2.0], known_rate=[0.0, 0.0], model_unknown_rate=[0.5, 0.5],
        unknown_stoichiometric_coefficient=-1.0, windows=[(1.0, 2.0)],
    )
    kwargs[field] = [0.0, bad]
    with pytest.raises(ValueError, match="finite"):
        build_integrated_flux_targets(**kwargs)


def test_elapsed_duration_does_not_depend_on_sample_density():
    assert duration_above_threshold([0, 10], [0, 10], threshold=5) == pytest.approx(5)
    assert duration_above_threshold([0, 1, 2, 5, 10], [0, 1, 2, 5, 10], threshold=5) == pytest.approx(5)
    assert duration_above_threshold([0, 10], [10, 0], threshold=5) == pytest.approx(5)


def test_reset_jumps_cannot_be_integrated_as_continuous_time():
    with pytest.raises(ValueError, match="strictly increasing"):
        duration_above_threshold([0, 1, 1, 4], [1, 0, 1, 0], threshold=0.5)
    total = duration_above_threshold([0, 1], [1, 0], threshold=0.5)
    total += duration_above_threshold([1, 4], [1, 0], threshold=0.5)
    assert total == pytest.approx(2.0)


def test_reset_aliases_cannot_overwrite_one_pool_twice():
    with pytest.raises(ValueError, match="aliases"):
        reset_observed_states([1.0], observations={"A": 2.0, "B": 3.0},
                              state_indices={"A": 0, "B": 0}, time_day=1)


@pytest.mark.parametrize("count", [0, -1, 1.5, True])
def test_forward_chaining_requires_positive_integer_interval_count(count):
    with pytest.raises(ValueError, match="positive integer"):
        forward_chaining_splits([1, 4, 8, 11, 15], minimum_training_intervals=count)


def test_replay_retains_raw_negative_state_evidence(monkeypatch):
    import profile_glycolysis_flux_bottlenecks as replay
    solution = SimpleNamespace(success=True, t=np.array([1.0, 2.0]), y=np.array([[0.1, -1e-5]]))
    monkeypatch.setattr(replay, "solve_ivp", lambda *args, **kwargs: solution)
    monkeypatch.setattr(replay, "equadiff_brodbar", lambda *args, **kwargs: [0.0])
    sol, _, _ = replay._simulate_and_track(params={}, t_eval=solution.t, method="BDF",
                                          rtol=1e-4, atol=1e-6, x0_override=np.array([0.1]))
    assert sol.raw_minimum_state_mM == -1e-5
    assert sol.negative_state_sample_count == 1
    assert sol.y.min() == 0.0


def test_source_stoichiometry_matches_full_positive_state_rhs():
    from review_fla_evidence import audit_rhs, NUM_BASE_METABOLITES, PHI_INDEX
    state = np.full(NUM_BASE_METABOLITES + 1, 0.2)
    state[PHI_INDEX] = 7.2
    result = audit_rhs(state)
    assert result["max_effective_balance_error_mM_per_day"] < 1e-10
    assert result["max_raw_stoichiometric_defect_mM_per_day"] < 1e-10


def test_digit_prefixed_reactions_have_complete_stoichiometry_and_scope():
    import rbc_stoichiometry as stoich
    assert stoich.STOICHIOMETRY["V6PGD"] == {"GO6P": -1.0, "RU5P": 1.0, "NADP": -1.0, "NADPH": 1.0}
    assert stoich.STOICHIOMETRY["V23DPGP"] == {"P3G": 1.0, "B23PG": -1.0}
    assert "V6PGD" in stoich.reactions_for_metabolites(["GO6P"])
    assert "V23DPGP" in stoich.reactions_for_metabolites(["B23PG"])
