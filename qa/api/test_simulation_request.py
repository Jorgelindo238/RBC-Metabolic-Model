import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for path in (
    PROJECT_ROOT,
    PROJECT_ROOT / "apps" / "api",
    PROJECT_ROOT / "streamlit_app",
    PROJECT_ROOT / "src",
):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from apps.api.routers.simulation import SimulationRequest


def test_simulation_request_rejects_one_day_horizon():
    with pytest.raises(ValidationError):
        SimulationRequest(t_max=1)


def test_simulation_request_accepts_two_day_horizon():
    request = SimulationRequest(t_max=2)

    assert request.t_max == 2
