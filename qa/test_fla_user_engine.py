"""Successor user engine: prepare/validate/run with injected RHS and solver. No ODE of the model runs.

Written on 2026-11-12 and NOT executed by their author.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import fla_user_engine as engine  # noqa: E402

NAMES = ("GLC", "ATP", "R5P", "EGLC", "PHI")
LAYOUT = {"GLC": "intracellular", "ATP": "intracellular", "R5P": "intracellular", "EGLC": "extracellular", "PHI": "intracellular"}
TIMES = [1.0, 4.0, 8.0]


def contract():
    return {
        "schema_version": engine.SCHEMA_VERSION,
        "dataset": {"dataset_id": "lab-a-1", "cohort_id": "lab-a", "subject": {"kind": "donor", "id": "d07"}},
        "time": {"unit": "day", "origin": {"kind": "collection", "description": "day 0 = collection"}, "points": list(TIMES)},
        "geometry": {"hematocrit": 0.6, "provenance": {"kind": "measured_this_dataset", "source": "unit record"}},
        "initial_state": {"policy": "user_declared_table", "time": 1.0, "unmeasured_pools_policy": "declared_latent_contract",
                          "values": [
                              {"name": "GLC", "compartment": "intracellular", "unit": "mM", "value": 1.2, "status": "measured", "source": "assay"},
                              {"name": "ATP", "compartment": "intracellular", "unit": "mM", "value": 0.9, "status": "measured", "source": "assay"},
                              {"name": "R5P", "compartment": "intracellular", "unit": "mM", "value": 0.01, "status": "latent_declared",
                               "source": "declared latent, see latent contract"},
                              {"name": "EGLC", "compartment": "extracellular", "unit": "mM", "value": 25.0, "status": "measured", "source": "assay"},
                              {"name": "PHI", "compartment": "intracellular", "unit": "pH", "value": 7.2, "status": "latent_declared", "source": "clamped"},
                          ]},
        "channels": [
            {"name": "GLC", "compartment": "intracellular", "kind": "absolute", "unit": "mM", "values": [1.2, 1.3, None]},
            {"name": "ATP", "compartment": "intracellular", "kind": "absolute", "unit": "mM", "values": [0.9, 1.0, 1.1]},
            {"name": "EGLC", "compartment": "extracellular", "kind": "absolute", "unit": "mM", "values": [25.0, 24.0, 22.0]},
        ],
    }


def request(**overrides):
    base = {"parameters": {"vmax_VHK": 0.1, "km_GLC": 0.2, "ki_ATP_PK": 1.7, "sam_adenylate_stoichiometry": "biochemical_transfer"},
            "parameters_source": "test vector", "kinetics": {"conductance": 0.03, "km_i": 3.5, "km_e": 23.5},
            "backend": "joint", "network_mode": "native", "threshold_mM": 1e-3, "negative_tolerance_mM": -1e-10,
            "solver": {"method": "Radau", "rtol": 1e-8, "atol": 1e-12}}
    base.update(overrides)
    return base


def prepared(c=None, r=None):
    return engine.prepare(c or contract(), r or request(), pool_names=NAMES, compartments=LAYOUT)


def transport_rhs(h, k=0.05):
    """GLC <-> EGLC carrier with cell-normalized extent, scaled per phase as in phase_matrix."""
    vi, ve = h, 1 - h

    def rhs(t, x):
        v = k * (x[3] - x[0])
        d = np.zeros_like(x)
        d[0], d[3] = v, -v * vi / ve
        return d
    return rhs


def euler(rhs, t_span, y0, *, t_eval, steps=200, **settings):
    y, t, out = np.array(y0, float), t_span[0], [np.array(y0, float)]
    for target in t_eval[1:]:
        dt = (target - t) / steps
        for _ in range(steps):
            y = y + dt * rhs(t, y)
            t += dt
        t = float(target)
        out.append(y.copy())
    return SimpleNamespace(success=True, t=np.array(t_eval, float), y=np.array(out).T, message="ok")


def factory_recording(log, h_rhs=True):
    def factory(**kwargs):
        log.append(kwargs)
        return transport_rhs(kwargs["hematocrit"]) if h_rhs else (lambda t, x: np.zeros_like(x))
    return factory


def codes(error):
    return [i["code"] for i in error.value.issues]


# --- prepare ---------------------------------------------------------------

def test_prepare_builds_a_complete_locked_state_without_loading_anything():
    p = prepared()
    assert p.initial_state == (1.2, 0.9, 0.01, 25.0, 7.2)
    assert p.measured_locked == {"GLC": 1.2, "ATP": 0.9, "EGLC": 25.0}
    assert p.provenance["R5P"] == {"status": "latent_declared", "source": "declared latent, see latent contract"}
    assert p.t0 == 1.0 and p.sample_times == (1.0, 4.0, 8.0) and p.hematocrit == 0.6
    assert p.flags["implicit_reference_loading"] is False and p.flags["parameter_search"] is False
    assert p.flags["qualification"] == "not_qualified" == engine.QUALIFICATION_STATUS
    assert engine.validate(p)["valid"]


def test_prepare_does_not_modify_its_inputs():
    c, r = contract(), request()
    snapshot = deepcopy((c, r))
    engine.prepare(c, r, pool_names=NAMES, compartments=LAYOUT)
    assert (c, r) == snapshot


@pytest.mark.parametrize("names, layout", [((), LAYOUT), (NAMES, {**LAYOUT, "GLC": "plasma"}), (NAMES + ("GLC",), LAYOUT),
                                           (NAMES, {k: v for k, v in LAYOUT.items() if k != "R5P"})])
def test_model_layout_is_required_and_checked(names, layout):
    with pytest.raises(engine.EngineContractError) as error:
        engine.prepare(contract(), request(), pool_names=names, compartments=layout)
    assert codes(error) == ["model_layout_invalid"]


def test_missing_states_are_refused_never_filled_with_a_default():
    c = contract(); c["initial_state"]["values"] = [v for v in c["initial_state"]["values"] if v["name"] != "R5P"]
    with pytest.raises(engine.EngineContractError) as error:
        prepared(c)
    assert "initial_state_incomplete" in codes(error)


def test_only_a_complete_declared_table_is_accepted():
    c = contract(); c["initial_state"]["policy"] = "user_measured_at_first_time"
    with pytest.raises(engine.EngineContractError) as error:
        prepared(c)
    assert "complete_initial_state_required" in codes(error)


@pytest.mark.parametrize("change, code", [
    (lambda c: c["initial_state"]["values"][0].update(value=1.25), "measured_initial_value_mismatch"),
    (lambda c: c["initial_state"]["values"][0].update(status="latent_declared"), "observed_state_not_marked_measured"),
    (lambda c: c["initial_state"]["values"][2].update(status="measured"), "measured_without_observation"),
    (lambda c: c["initial_state"]["values"][2].update(source=""), "state_source_missing"),
    (lambda c: c["initial_state"]["values"][2].update(unit="uM"), "state_unit_invalid"),
    (lambda c: c["initial_state"]["values"][4].update(unit="mM"), "state_unit_invalid"),
    (lambda c: c["initial_state"]["values"][3].update(compartment="intracellular"), "state_compartment_mismatch"),
    (lambda c: c["initial_state"]["values"].append(dict(c["initial_state"]["values"][1])), "state_declared_twice"),
    (lambda c: c["initial_state"]["values"].append({"name": "E4P", "compartment": "intracellular", "unit": "mM",
                                                    "value": 0.1, "status": "latent_declared", "source": "x"}), "unknown_state"),
    (lambda c: c["initial_state"].update(time=0.0), "initial_state_not_at_first_sample"),
])
def test_initial_state_entries_are_checked_against_the_measured_lock(change, code):
    c = contract(); change(c)
    with pytest.raises(engine.EngineContractError) as error:
        prepared(c)
    assert code in codes(error)


@pytest.mark.parametrize("change, code", [
    (lambda c: c["channels"].append({"name": "R5P", "compartment": "intracellular", "kind": "relative", "unit": "fold_change",
                                     "values": [1.0, 1.1, 1.2], "normalization": {"basis": "first_point", "description": "x"}}),
     "relative_channel_blocked"),
    (lambda c: c["channels"][1].update(unit="uM", values=[900.0, 1000.0, 1100.0]), "channel_unit_not_mM"),
    (lambda c: c["channels"][2].update(compartment="intracellular"), "channel_compartment_mismatch"),
    (lambda c: c["channels"].append(dict(c["channels"][1])), "channel_duplicated"),
    (lambda c: c["channels"][1].update(values=[0.9, 1.0]), "channel_values_invalid"),
    (lambda c: c["dataset"].update(donors=["d07", "d08"]), "multiple_subjects_in_one_run"),
    (lambda c: c["dataset"]["subject"].update(id=""), "identity_missing"),
    (lambda c: c["geometry"].pop("hematocrit"), "hematocrit_invalid"),
    (lambda c: c["geometry"]["provenance"].update(source=""), "geometry_provenance_missing"),
    (lambda c: c["time"].update(points=[1.0, 1.0, 8.0]), "time_points_not_increasing"),
    (lambda c: c["time"].update(unit="hour"), "time_unit_invalid"),
    (lambda c: c.update(schema_version="airbc.user_calibration_data/2"), "schema_version_unsupported"),
])
def test_data_outside_the_engine_scope_is_refused(change, code):
    c = contract(); change(c)
    with pytest.raises(engine.EngineContractError) as error:
        prepared(c)
    assert code in codes(error)


def test_a_dataset_with_nothing_after_the_first_sample_is_refused():
    c = contract()
    for channel in c["channels"]:
        channel["values"] = [channel["values"][0], None, None]
    with pytest.raises(engine.EngineContractError) as error:
        prepared(c)
    assert "nothing_to_score" in codes(error)


@pytest.mark.parametrize("overrides, code", [
    ({"parameters": {}}, "parameters_missing"),
    ({"parameters_source": ""}, "parameters_source_missing"),
    ({"parameters": {"vmax_VHK": float("nan")}}, "parameter_invalid"),
    ({"parameters": {"vmax_VPK": 1.0, "kinetic_family_VPK": "teacher_curve_pchip"}}, "teacher_forced_kinetics"),
    ({"kinetics": {}}, "kinetics_missing"),
    ({"backend": "fast"}, "backend_invalid"),
    ({"network_mode": ""}, "network_mode_missing"),
    ({"threshold_mM": 0.0}, "threshold_mM_invalid"),
    ({"negative_tolerance_mM": 1e-6}, "negative_tolerance_mM_invalid"),
    ({"solver": {"method": "Radau"}}, "solver_settings_missing"),
    ({"solver": {"method": "Radau", "rtol": 1e-8, "atol": 1e-12, "t_eval": [0.0]}}, "solver_controls_time_or_state"),
    ({"params_to_optimize": {"vmax_VHK": [1, 0, 2]}}, "forbidden_request_key"),
    ({"t_max": 46}, "forbidden_request_key"),
])
def test_engine_request_is_explicit_and_fixed(overrides, code):
    with pytest.raises(engine.EngineContractError) as error:
        prepared(r=request(**overrides))
    assert code in codes(error)


def test_every_issue_is_reported_at_once():
    c = contract(); c["geometry"].pop("hematocrit"); c["channels"][1]["unit"] = "uM"
    with pytest.raises(engine.EngineContractError) as error:
        prepared(c, request(backend="fast"))
    assert {"hematocrit_invalid", "channel_unit_not_mM", "backend_invalid"} <= set(codes(error))


def test_different_donors_give_different_fingerprints_and_are_never_merged():
    a = prepared()
    c = contract(); c["dataset"]["subject"]["id"] = "d08"
    b = prepared(c)
    assert a.fingerprint != b.fingerprint and a.identity["subject_id"] == "d07" and b.identity["subject_id"] == "d08"
    assert a.flags["donors_merged"] is False


# --- run ---------------------------------------------------------------------

def test_run_requires_explicit_factory_and_solver():
    with pytest.raises(TypeError):
        engine.run(prepared())


def test_run_passes_declared_geometry_mode_and_an_equal_parameter_copy_to_the_rhs():
    log = []
    p = prepared()
    result = engine.run(p, rhs_factory=factory_recording(log), solver=euler)
    assert result["status"] == "completed_unqualified"
    call = log[0]
    assert call["hematocrit"] == 0.6 and call["mode"] == "native" and call["backend"] == "joint" and call["threshold"] == 1e-3
    assert call["parameters"] == p.parameters and call["parameters"] is not p.parameters
    assert call["parameters"]["km_GLC"] == 0.2 and call["parameters"]["ki_ATP_PK"] == 1.7
    assert result["parameters_unchanged"] and result["parameter_search"] is False


def test_first_sample_state_is_the_declared_state_bit_for_bit():
    result = engine.run(prepared(), rhs_factory=factory_recording([]), solver=euler)
    states = result["states_at_samples"]
    assert [states[n][0] for n in NAMES] == [1.2, 0.9, 0.01, 25.0, 7.2]
    assert result["first_sample_identity"] and result["measured_locked"] == {"GLC": 1.2, "ATP": 0.9, "EGLC": 25.0}


def test_transport_conserves_bag_amounts_with_distinct_phase_volumes():
    p = prepared()
    result = engine.run(p, rhs_factory=factory_recording([]), solver=euler)
    y = np.array([result["states_at_samples"][n] for n in NAMES])
    amounts = engine.bag_amounts(y, NAMES, LAYOUT, p.hematocrit)
    glucose = amounts[0] + amounts[3]
    assert np.allclose(glucose, glucose[0], rtol=0, atol=1e-10)
    assert not np.allclose(y[0] + y[3], (y[0] + y[3])[0], rtol=0, atol=1e-6)
    assert np.all(amounts[NAMES.index("PHI")] == 0)


def test_bag_amounts_use_h_and_one_minus_h():
    amounts = engine.bag_amounts([2.0, 0.0, 0.0, 10.0, 7.2], NAMES, LAYOUT, 0.6)
    assert amounts.tolist() == pytest.approx([1.2, 0.0, 0.0, 4.0, 0.0])


def test_nothing_is_computed_before_the_first_sample_and_only_sample_dates_are_requested():
    seen = {}

    def spy(rhs, t_span, y0, *, t_eval, **settings):
        seen.update(t_span=t_span, t_eval=list(t_eval), settings=settings)
        return euler(rhs, t_span, y0, t_eval=t_eval)

    engine.run(prepared(), rhs_factory=factory_recording([]), solver=spy)
    assert seen["t_span"] == (1.0, 8.0) and seen["t_eval"] == TIMES
    assert seen["settings"] == {"method": "Radau", "rtol": 1e-8, "atol": 1e-12}


def test_a_solver_returning_an_earlier_time_is_a_contract_violation():
    def early(rhs, t_span, y0, *, t_eval, **settings):
        s = euler(rhs, t_span, y0, t_eval=t_eval)
        s.t = np.array([0.0, 4.0, 8.0])
        return s

    result = engine.run(prepared(), rhs_factory=factory_recording([]), solver=early)
    assert result["status"] == "contract_violation" and "before the first sample" in result["reason"]


def test_only_observed_dates_after_the_first_sample_are_scored():
    result = engine.run(prepared(), rhs_factory=factory_recording([], h_rhs=False), solver=euler)
    points = {(r["pool"], r["time"]) for r in result["residuals"]}
    assert points == {("GLC", 4.0), ("ATP", 4.0), ("ATP", 8.0), ("EGLC", 4.0), ("EGLC", 8.0)}
    assert result["scored_points"] == 5 and all(r["time"] > 1.0 for r in result["residuals"])
    assert result["sum_squared_residual_mM2"] == pytest.approx(0.1**2 + 0.1**2 + 0.2**2 + 1.0**2 + 3.0**2)


def test_rhs_that_mutates_its_parameters_is_a_contract_violation():
    def mutating(**kwargs):
        kwargs["parameters"]["km_GLC"] = 0.3
        return lambda t, x: np.zeros_like(x)

    result = engine.run(prepared(), rhs_factory=mutating, solver=euler)
    assert result["status"] == "contract_violation" and "parameters changed" in result["reason"]


def test_solver_that_changes_the_initial_state_is_a_contract_violation():
    def shifted(rhs, t_span, y0, *, t_eval, **settings):
        s = euler(rhs, t_span, y0, t_eval=t_eval)
        s.y[1, 0] += 1e-15
        return s

    assert engine.run(prepared(), rhs_factory=factory_recording([]), solver=shifted)["status"] == "contract_violation"


@pytest.mark.parametrize("solver, reason", [
    (lambda rhs, t_span, y0, *, t_eval, **s: SimpleNamespace(success=False, t=np.array(t_eval), y=None, message="step size too small"),
     "step size too small"),
    (lambda rhs, t_span, y0, *, t_eval, **s: SimpleNamespace(success=True, t=np.array(t_eval),
                                                            y=np.tile(np.array(y0)[:, None], 3) * [1, np.nan, 1], message=""),
     "non-finite"),
    (lambda rhs, t_span, y0, *, t_eval, **s: SimpleNamespace(success=True, t=np.array(t_eval),
                                                            y=np.tile(np.array(y0)[:, None], 3) - [0, 0, 1.0], message=""),
     "negative concentration"),
])
def test_numerical_failures_are_reported_not_raised(solver, reason):
    result = engine.run(prepared(), rhs_factory=factory_recording([]), solver=solver)
    assert result["status"] == "numerical_failure" and reason in result["reason"]


def test_solver_exception_and_rhs_refusal_are_reported():
    def boom(*args, **kwargs):
        raise RuntimeError("Jacobian singular")

    assert engine.run(prepared(), rhs_factory=factory_recording([]), solver=boom)["status"] == "numerical_failure"

    def refuse(**kwargs):
        raise ValueError("unknown GEM correction mode")

    assert engine.run(prepared(), rhs_factory=refuse, solver=euler)["status"] == "contract_violation"


def test_a_completed_run_is_never_validated_or_activatable():
    result = engine.run(prepared(), rhs_factory=factory_recording([]), solver=euler)
    assert result["status"] == "completed_unqualified" and result["qualification"] == "not_qualified"
    assert result["biologically_validated"] is False and result["activation_allowed"] is False
    assert result["free_ode"] is True and result["teacher_forcing"] is False


def test_invalid_prepared_run_is_not_executed():
    import dataclasses

    broken = dataclasses.replace(prepared(), parameters_sha256="0" * 64)

    def forbidden(**kwargs):
        pytest.fail("an invalid prepared run must not build an RHS")

    result = engine.run(broken, rhs_factory=forbidden, solver=euler)
    assert result["status"] == "invalid_prepared" and result["validation"]["checks"]["parameters_unchanged"] is False


def test_module_level_imports_are_standard_library_and_numpy_only():
    import ast

    tree = ast.parse(Path(engine.__file__).read_text(encoding="utf-8"))
    top = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            top.add((node.module or "").split(".")[0])
    assert top <= {"__future__", "copy", "dataclasses", "hashlib", "json", "math", "typing", "numpy"}
