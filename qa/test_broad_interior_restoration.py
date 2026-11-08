from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from restore_broad_interior import interior_step


def test_restoration_reaches_inner_target_without_widening_bounds():
    bounds = np.array([[-1., 1.], [-1., 0.]])
    x = np.array([0., -.5])
    jacobian = np.array([[1., 0.], [0., -1.]])
    margins = np.array([-1e-8, 0.])
    target = np.array([1e-5, 1e-5])
    result = interior_step(margins, jacobian, target, x, bounds, .005)
    assert result.success
    step = result.x[:2]
    assert np.all(margins+jacobian@step >= target-1e-10)
    assert np.all(x+step >= bounds[:, 0]) and np.all(x+step <= bounds[:, 1])


def test_incompatible_linearized_inner_target_is_not_relaxed():
    result = interior_step(np.zeros(2), np.array([[1.], [-1.]]), np.ones(2)*.1,
                           np.zeros(1), np.array([[-1., 1.]]), .005)
    assert not result.success
