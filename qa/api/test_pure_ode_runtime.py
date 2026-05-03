import csv

import numpy as np

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
