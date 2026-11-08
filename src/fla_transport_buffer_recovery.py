"""Bounded clean recovery for the frozen closed toy, never biological fitting."""

import copy
import itertools

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares

from fla_transport_buffer_synthetic import rhs, validate_config

STAGES = {
    "oracle_conductance": (("conductance",), ("concentrations",)),
    "conductance_buffer": (("conductance", "beta_e"),
                           ("concentrations_plus_pHe", "concentrations_plus_pHi_pHe")),
    "access_pHi": (("access_i", "phi0"),
                   ("concentrations", "concentrations_plus_pHe", "concentrations_plus_pHi_pHe")),
}


def training_times(config, schedule):
    if schedule == "sparse":
        return np.array([t for t in config["sparse_days"] if t <= config["training_end_day"]])
    if schedule == "dense":
        return np.linspace(config["horizon_day"][0], config["training_end_day"], config["dense_training_count"])
    raise ValueError("unknown training schedule")


def scales(config, rows):
    scaling = config["sensitivity_scaling"]
    return np.array([scaling["concentration_mM"]] * 2 + [scaling["pH_units"]] * 2)[list(rows)]


def select_saved(time, states, query):
    time, states, query = map(lambda x: np.asarray(x, dtype=float), (time, states, query))
    if (time.ndim != 1 or states.shape != (5, len(time)) or query.ndim != 1
            or not len(query) or not np.all(np.isfinite(time)) or not np.all(np.isfinite(states))
            or not np.all(np.isfinite(query)) or np.any(np.diff(time) <= 0) or np.any(np.diff(query) <= 0)):
        raise ValueError("finite ordered saved observations required")
    indices = np.searchsorted(time, query)
    if np.any(indices >= len(time)) or not np.array_equal(time[indices], query):
        raise ValueError("only exact saved query coordinates are allowed; no interpolation")
    return states[:, indices].copy()


def encode(names, values):
    return np.array([values[n] if n == "phi0" else np.log(values[n]) for n in names])


def decode(names, coordinates):
    coordinates = np.asarray(coordinates, dtype=float)
    if coordinates.shape != (len(names),) or not np.all(np.isfinite(coordinates)):
        raise ValueError("finite parameter vector required")
    return {n: float(v if n == "phi0" else np.exp(v)) for n, v in zip(names, coordinates)}


class EvaluationBudgetReached(RuntimeError):
    pass


class TrainingObjective:
    """The optimizer sees only training data; unknown initial pHi is always replaced."""

    def __init__(self, config, scenario, stage, plan, time, observations):
        validate_config(config)
        if stage not in STAGES or plan not in STAGES[stage][1]:
            raise ValueError("undeclared recovery scope")
        self.config, self.scenario = copy.deepcopy(config), copy.deepcopy(scenario)
        self.names = STAGES[stage][0]
        self.rows = tuple(config["observation_plans"][plan])
        self.time = np.asarray(time, dtype=float).copy()
        self.observations = np.asarray(observations, dtype=float).copy()
        if (self.time.ndim != 1 or len(self.time) < 2 or not np.all(np.isfinite(self.time))
                or np.any(np.diff(self.time) <= 0) or self.time[0] != config["horizon_day"][0]
                or self.time[-1] > config["training_end_day"]
                or self.observations.shape != (len(self.rows), len(self.time))
                or not np.all(np.isfinite(self.observations))
                or np.any(self.observations[:2] < 0)):
            raise ValueError("only finite nonnegative aligned training observations are allowed")
        self.scale = scales(config, self.rows)
        self.limit = config["future_recovery"]["optimizer_budget_max_nfev"]
        if type(self.limit) is not int or self.limit <= 0:
            raise ValueError("positive integer evaluation budget required")
        self.trace, self.best = [], None

    def evaluate(self, coordinates):
        if len(self.trace) >= self.limit:
            raise EvaluationBudgetReached("actual objective evaluations exhausted")
        parameters = decode(self.names, coordinates)
        truth = {**self.config["truth"], **{k: v for k, v in parameters.items() if k != "phi0"}}
        initial = np.array(self.scenario["initial"], dtype=float)
        if "phi0" in self.names:
            initial[2] = parameters["phi0"]
        end = self.config["training_end_day"]
        sol = solve_ivp(lambda t, x: rhs(t, x, h=self.config["geometry"]["hematocrit"], truth=truth),
                        (self.config["horizon_day"][0], end), initial, method="BDF", dense_output=True,
                        **self.config["solver_profiles"]["ultrastrict"])
        if not sol.success or sol.t[-1] != end:
            raise ValueError("incomplete training integration: " + sol.message)
        states = sol.sol(self.time)
        if not np.all(np.isfinite(states)) or min(states[:2].min(), sol.y[:2].min()) < 0:
            raise ValueError("invalid training trajectory; no clipping or finite penalty replacement")
        residual = ((states[list(self.rows)] - self.observations) / self.scale[:, None]).ravel()
        cost = float(np.dot(residual, residual))
        self.trace.append({"parameters": parameters, "sum_squared_scaled_residual": cost,
                           "integration_end": float(sol.t[-1])})
        if self.best is None or cost < self.best[0]:
            self.best = cost, parameters
        return residual


def recover(config, scenario, stage, plan, time, observations, start_index):
    objective = TrainingObjective(config, scenario, stage, plan, time, observations)
    future = config["future_recovery"]
    names = objective.names
    if type(start_index) is not int or not 0 <= start_index < len(future["start_vectors"]):
        raise ValueError("prespecified start index required")
    start = dict(zip(future["start_parameter_order"], future["start_vectors"][start_index]))
    bounds = future["parameter_bounds"]
    lower, upper = [{n: bounds[n][j] for n in names} for j in (0, 1)]
    x0, lo, hi = encode(names, start), encode(names, lower), encode(names, upper)
    if not np.all(np.isfinite(np.r_[x0, lo, hi])) or np.any(x0 <= lo) or np.any(x0 >= hi):
        raise ValueError("declared start must lie strictly within the declared bounds")
    # Count finite-difference calls too: scipy's nfev alone excludes them.
    try:
        fit = least_squares(objective.evaluate, x0, bounds=(lo, hi), jac="3-point",
                            diff_step=config["finite_difference_steps"][0], x_scale=1.0,
                            max_nfev=objective.limit, ftol=1e-10, xtol=1e-10, gtol=1e-10)
        parameters = decode(names, fit.x)
        success, message, nfev = bool(fit.success), str(fit.message), int(fit.nfev)
    except EvaluationBudgetReached as exc:
        parameters = objective.best[1]
        success, message, nfev = False, str(exc), None
    return {"stage": stage, "plan": plan, "scenario": scenario["name"], "start_index": start_index,
            "free_parameters": list(names), "fixed_other_inputs": "known_synthetic_context_not_learned_biological_evidence",
            "start_parameters": {n: start[n] for n in names}, "parameters": parameters,
            "optimizer_success": success, "optimizer_message": message, "scipy_nfev": nfev,
            "actual_objective_evaluations": len(objective.trace), "evaluation_budget": objective.limit,
            "training_days": objective.time.tolist(), "trace": objective.trace,
            "solver": "BDF_ultrastrict", "jacobian": "3-point", "diff_step": config["finite_difference_steps"][0],
            "xtol": 1e-10, "ftol": 1e-10, "gtol": 1e-10, "x_scale": 1.0}


def parameter_errors(config, scenario, parameters):
    future = config["future_recovery"]
    errors, checks = {}, {}
    for name, value in parameters.items():
        if name == "phi0":
            error, limit = abs(value - scenario["initial"][2]), future["clean_phi0_absolute_error_limit"]
        else:
            error = abs(value / config["truth"][name] - 1)
            limit = future["clean_parameter_relative_error_limit"]
        errors[name], checks[name] = float(error), bool(error <= limit)
    return errors, all(checks.values())


def prediction_metrics(config, scenario, parameters, result, reference):
    if not np.array_equal(result["time"], reference["time"]):
        raise ValueError("aligned prediction reference required")
    names = ("LAC", "ELAC", "pHi", "pHe")
    indices = {"training": result["time"] <= config["training_end_day"],
               "holdout": result["time"] > config["training_end_day"]}
    errors, parameters_pass = parameter_errors(config, scenario, parameters)
    metrics = {"parameter_errors": errors, "parameter_recovery_pass": parameters_pass}
    for period, mask in indices.items():
        if not np.any(mask):
            raise ValueError("both training and untouched holdout predictions required")
        delta = result["states"][:4, mask] - reference["states"][:4, mask]
        metrics[period + "_rmse"] = dict(zip(names, np.sqrt(np.mean(delta**2, axis=1)).tolist()))
        metrics[period + "_scaled_RMSE_all_states"] = float(np.sqrt(np.mean((delta / scales(config, range(4))[:, None])**2)))
    metrics["holdout_prediction_pass"] = bool(metrics["holdout_scaled_RMSE_all_states"]
                                               <= config["future_recovery"]["clean_holdout_scaled_RMSE_limit"])
    return metrics


def multistart_agreement(config, fits):
    if not fits or len(fits) != len(config["future_recovery"]["start_vectors"]):
        raise ValueError("all prespecified starts required")
    if sorted(f["start_index"] for f in fits) != list(range(len(fits))):
        raise ValueError("starts must be unique and complete")
    spreads = {}
    for name in fits[0]["parameters"]:
        pairs = itertools.combinations([f["parameters"][name] for f in fits], 2)
        spreads[name] = max(abs(a - b) if name == "phi0" else abs(a - b) / max(abs(a), abs(b)) for a, b in pairs)
    agreement = all(v <= config["future_recovery"]["clean_phi0_absolute_error_limit" if n == "phi0"
                                                        else "clean_parameter_relative_error_limit"] for n, v in spreads.items())
    return {"parameter_spreads": spreads, "multistart_agreement_pass": bool(agreement)}
