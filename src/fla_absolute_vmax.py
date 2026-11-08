"""Absolute late adenylate feasibility, retaining the dated metabolic guards."""

import numpy as np

from fla_temporal_vmax import evaluate_panel


def target_spec(panel, plan):
    if plan["target_pools"] != ["ATP", "ADP"] or plan["target_day"] != 15:
        raise ValueError("registered J15 ATP/ADP targets required")
    if plan["target_band"] != "inherited_working_scale":
        raise ValueError("reuse the declared working band, not an assay SD")
    j = panel["days"].index(plan["target_day"])
    result = {}
    for pool in plan["target_pools"]:
        i = panel["names"].index(pool)
        y, band = float(panel["target"][i,j]), float(panel["bands"][i,j])
        if not 0 < band < y:
            raise ValueError("finite positive target interval required")
        result[pool] = {"day": plan["target_day"], "nominal_mM": y,
                        "band_mM": band, "lower_mM": y-band, "upper_mM": y+band}
    return result


def absolute_score(prediction, panel, targets):
    x = np.asarray(prediction, float)
    if x.shape != panel["target"].shape or not np.isfinite(x).all():
        raise ValueError("invalid concentration panel")
    sides, concentrations = {}, {}
    for pool, t in targets.items():
        value = float(x[panel["names"].index(pool), panel["days"].index(t["day"])])
        if value <= 0:
            raise ValueError("positive adenylates required; no pseudocount")
        concentrations[pool] = value
        sides[pool+":lower"] = float(np.log(t["lower_mM"]/value))
        sides[pool+":upper"] = float(np.log(value/t["upper_mM"]))
    objective = max(sides.values())
    return {"objective": objective, "sides": sides, "concentrations_mM": concentrations,
            "target_pass": bool(objective <= 0)}


def evaluate_screen(prediction, reference, panel, design, temporal, targets):
    result = evaluate_panel(prediction, reference, panel, design, temporal)
    guards = dict(result["guards"])
    for day, ratio in zip(panel["days"], result["day_ratios"]):
        guards[f"date_gain:J{day}"] = float(ratio-1+temporal["minimum_each_day_relative_gain"])
    return {**result, "absolute": absolute_score(prediction, panel, targets),
            "feasibility_guards": guards,
            "feasibility_guards_pass": bool(max(guards.values()) <= 0)}
