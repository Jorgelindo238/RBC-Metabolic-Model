import csv

import numpy as np
import pytest

from apps.api.services.pure_ode_runtime import write_simulation_artifacts


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def test_simulation_artifact_writer_accepts_numpy_arrays(tmp_path):
    result = {
        "success": True,
        "metabolite_names": np.array(["ATP", "ADP"]),
        "t": np.array([0.0, 1.0]),
        "x": np.array([[1.0, 0.2], [0.9, 0.25]]),
        "flux_data": {
            "times": np.array([0.0, 1.0]),
            "fluxes": {
                "VHK": np.array([0.1, 0.2]),
                "VLDH": np.array([0.3, 0.4]),
            },
        },
    }

    artifacts = write_simulation_artifacts(result, tmp_path)

    metabolite_rows = _read_csv(artifacts["all_metabolites_csv"])
    flux_rows = _read_csv(artifacts["reaction_fluxes_csv"])

    assert metabolite_rows == [
        ["Time", "ATP", "ADP"],
        ["0.0", "1.0", "0.2"],
        ["1.0", "0.9", "0.25"],
    ]
    assert flux_rows == [
        ["time", "VHK", "VLDH"],
        ["0.0", "0.1", "0.3"],
        ["1.0", "0.2", "0.4"],
    ]


@pytest.mark.parametrize("field,value", [
    ("x", [[1.0]]),
    ("x", [1.0, 0.9]),
    ("x", [[1.0], [float("nan")]]),
    ("x", [[1.0, 2.0], [1.0, 2.0]]),
    ("t", [1.0, 0.0]),
    ("t", [0.0, float("inf")]),
    ("flux_data", {"times": [0.0, 1.0], "fluxes": {"VHK": [0.1]}}),
    ("flux_data", {"times": [0.0, 1.0], "fluxes": {"VHK": [0.1, float("nan")]}}),
    ("flux_data", {"times": [0.0, 1.0], "fluxes": {}}),
])
def test_invalid_evidence_is_rejected_before_creating_artifacts(tmp_path, field, value):
    result = {"metabolite_names": ["ATP"], "t": [0.0, 1.0], "x": [[1.0], [0.9]]}
    result[field] = value
    with pytest.raises(ValueError):
        write_simulation_artifacts(result, tmp_path)
    assert list(tmp_path.rglob("*.csv")) == []


def test_signed_fluxes_and_raw_tracker_step_order_are_preserved(tmp_path):
    result = {
        "metabolite_names": ["ATP"], "t": [0.0, 1.0], "x": [[1.0], [0.9]],
        "flux_data": {"times": [0.0, 0.2, 0.1], "fluxes": {"VAK": [0.1, -0.3, 0.2]}},
    }
    paths = write_simulation_artifacts(result, tmp_path)
    assert _read_csv(paths["reaction_fluxes_csv"])[2] == ["0.2", "-0.3"]
