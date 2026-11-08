"""Alternative observation objective on the sealed synthetic transport panels."""

import numpy as np
from scipy.optimize import least_squares

from fla_observation_likelihood import mixed_assay_likelihood
from fla_transport_buffer_recovery import (TrainingObjective, EvaluationBudgetReached, encode, decode)


class MatchedObjective(TrainingObjective):
    def evaluate(self, coordinates):
        previous_best = self.best
        base = super().evaluate(coordinates).reshape(self.observations.shape)
        predicted = self.observations+base*self.scale[:, None]
        mask = np.ones(predicted.shape, dtype=bool)
        for i, row in enumerate(self.rows):
            if row < 2:
                mask[i, 0] = False
        future = self.config["future_recovery"]
        likelihood = mixed_assay_likelihood(predicted, self.observations, self.rows,
            concentration_cv=future["synthetic_concentration_CV"], ph_sd=future["synthetic_pH_SD"], mask=mask)
        residual = likelihood["residuals"]
        cost = float(np.dot(residual, residual))
        self.trace[-1]["original_design_sum_squared_residual"] = self.trace[-1]["sum_squared_scaled_residual"]
        self.trace[-1]["sum_squared_scaled_residual"] = cost
        self.trace[-1]["negative_log_likelihood"] = likelihood["negative_log_likelihood"]
        self.trace[-1]["stochastic_terms"] = likelihood["terms"]
        self.best = (cost, self.trace[-1]["parameters"]) if previous_best is None or cost < previous_best[0] else previous_best
        return residual


def recover_objective(config, scenario, stage, plan, time, observations, start_index, *, kind, budget):
    if kind not in ("current_cost", "matched_likelihood") or type(budget) is not int or budget <= 0:
        raise ValueError("declared objective and positive integer budget required")
    objective = (MatchedObjective if kind == "matched_likelihood" else TrainingObjective)(
        config, scenario, stage, plan, time, observations)
    objective.limit = budget
    future, names = config["future_recovery"], objective.names
    if type(start_index) is not int or not 0 <= start_index < len(future["start_vectors"]):
        raise ValueError("prespecified start required")
    start = dict(zip(future["start_parameter_order"], future["start_vectors"][start_index]))
    bounds = future["parameter_bounds"]
    lo, hi = [encode(names, {n: bounds[n][j] for n in names}) for j in (0, 1)]
    x0 = encode(names, start)
    if np.any(x0 <= lo) or np.any(x0 >= hi):
        raise ValueError("interior start required")
    try:
        fit = least_squares(objective.evaluate, x0, bounds=(lo, hi), jac="3-point",
            diff_step=config["finite_difference_steps"][0], x_scale=1.0, max_nfev=budget,
            ftol=1e-10, xtol=1e-10, gtol=1e-10)
        params, success, message, nfev = decode(names, fit.x), bool(fit.success), str(fit.message), int(fit.nfev)
    except EvaluationBudgetReached as exc:
        params, success, message, nfev = objective.best[1], False, str(exc), None
    return {"stage": stage, "plan": plan, "scenario": scenario["name"], "start_index": start_index,
        "objective_kind": kind, "evaluation_budget": budget, "parameters": params,
        "start_parameters": {n: start[n] for n in names}, "free_parameters": list(names),
        "fixed_other_inputs": "known_synthetic_context_not_learned_biological_evidence",
        "optimizer_success": success, "optimizer_message": message, "scipy_nfev": nfev,
        "actual_objective_evaluations": len(objective.trace), "trace": objective.trace,
        "training_days": objective.time.tolist(), "solver": "BDF_ultrastrict", "jacobian": "3-point",
        "diff_step": config["finite_difference_steps"][0], "x_scale": 1.0, "ftol": 1e-10, "xtol": 1e-10, "gtol": 1e-10}
