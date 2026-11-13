"""Search perturbation direction and unchanged Vmax-only guards; no integrations."""
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_corrected_vmax import vector_step, read, exact_parameters, within_original_box


def test_difference_points_stay_in_original_box():
    f = read(ROOT / 'output/vmax_requalification_2026_11_09/execution_design.json')
    lo, hi = np.log([f['design']['factor_bounds'][k] for k in f['design']['groups']]).T
    x = np.array(f['profile_center'])
    steps = vector_step(x, hi, f['temporal']['difference_step_log'])
    for v in x + np.diag(steps):
        assert within_original_box(f, v)
        p = exact_parameters(f, v)
        assert all(k.startswith('vmax_') for k in p if p[k] != f['parameters'][k])
    assert steps[list(f['design']['groups']).index('PGK')] > 0
    assert steps[list(f['design']['groups']).index('NDPK')] < 0


def test_upper_boundary_uses_backward_difference():
    assert vector_step([1., 0.], [1., 1.], .006).tolist() == [-.006, .006]
