"""Descriptive executed ATP/adenylate bookkeeping on sealed trajectories.

Pure array functions: no model, integration or filesystem access. Nothing
here is a causal intervention; shares describe one trajectory.
"""

import numpy as np

from fla_executed_attribution import limiting_loss_attribution


def _check(rates, weights, intervals):
    rates, weights, intervals = np.asarray(rates, float), np.asarray(weights, float), np.asarray(intervals)
    if (rates.ndim != 2 or weights.shape != (rates.shape[1],) or intervals.shape != weights.shape
            or not np.isfinite(rates).all() or not np.isfinite(weights).all() or np.any(weights < 0)):
        raise ValueError("aligned finite quadrature rates, nonnegative weights and intervals required")
    return rates, weights, intervals


def window_mask(intervals, window):
    """Daily interval k spans day k+1 to k+2; window [a, b] uses intervals a-1 .. b-2."""
    start, end = window
    if not (float(start).is_integer() and float(end).is_integer() and 1 <= start < end):
        raise ValueError("windows must be whole-day intervals starting at day 1 or later")
    mask = (np.asarray(intervals) >= start-1) & (np.asarray(intervals) < end-1)
    if not mask.any():
        raise ValueError("window has no quadrature support")
    return mask


def signed_integrals(rates, weights, intervals, window):
    rates, weights, intervals = _check(rates, weights, intervals)
    use = window_mask(intervals, window)
    return rates[:, use]@weights[use]


def pool_ledger(coefficients, rates, weights, intervals, window):
    """Net, gross production and gross consumption of one (possibly lumped) pool by reaction.

    Gross terms use the sign of the instantaneous contribution, so a reaction
    that reverses inside the window is not netted away.
    """
    rates, weights, intervals = _check(rates, weights, intervals)
    c = np.asarray(coefficients, float)
    if c.shape != (rates.shape[0],) or not np.isfinite(c).all():
        raise ValueError("one finite coefficient per reaction required")
    use = window_mask(intervals, window)
    contribution = c[:, None]*rates[:, use]
    w = weights[use]
    return {"net": contribution@w, "production": np.maximum(contribution, 0)@w,
            "consumption": np.maximum(-contribution, 0)@w}


def shares(values):
    values = np.asarray(values, float)
    total = values.sum()
    return np.divide(values, total, out=np.zeros_like(values), where=total > 0)


def gate_loss(states, raw, executed, matrix, weights, intervals, window, threshold):
    """Raw minus executed integrals and their allocation to the limiting pools.

    Requires executed == raw * minimum consumer availability at every node;
    otherwise the allocation would not describe the executed model.
    """
    raw, weights, intervals = _check(raw, weights, intervals)
    executed, states, matrix = np.asarray(executed, float), np.asarray(states, float), np.asarray(matrix, float)
    if executed.shape != raw.shape or matrix.shape != (states.shape[0], raw.shape[0]) or states.shape[1] != raw.shape[1]:
        raise ValueError("states, matrix, raw and executed rates must align")
    use = window_mask(intervals, window)
    w = weights[use]
    lost, by_pool = np.zeros(raw.shape[0]), np.zeros(matrix.shape)
    for j in range(raw.shape[0]):
        a = limiting_loss_attribution(states, raw[j], matrix[:, j], threshold=threshold)
        if not np.allclose(raw[j]*a["factors"], executed[j], rtol=1e-9, atol=1e-14):
            raise ValueError("executed rate is not raw rate times minimum consumer availability")
        lost[j] = a["loss"][use]@w
        by_pool[:, j] = a["loss_by_pool"][:, use]@w
    return {"raw": np.abs(raw[:, use])@w, "executed": np.abs(executed[:, use])@w, "lost": lost, "lost_by_pool": by_pool}


def cycle_accounts(integral, reactions, cycles):
    """Registered pathway accounts from signed executed integrals of named reactions."""
    v = {r: float(integral[reactions.index(r)]) for r in reactions}
    pnc = [v[r] for r in cycles["purine_nucleotide_cycle"]]
    n = cycles["NDPK_coupling"]
    p = cycles["PRPP"]
    g = cycles["glycolytic_yield"]
    rl = cycles["rapoport_luebering"]
    invest, ret = sum(v[r] for r in g["investment"]), sum(v[r] for r in g["return"])
    outflow = v[rl["bypass"]]+v[rl["direct"]]
    return {
        "purine_nucleotide_cycle": {**dict(zip(cycles["purine_nucleotide_cycle"], pnc)),
                                    "throughput_mM": max(min(pnc), 0.), "GTP_cost_mM": v["VADSS"]},
        "NDPK_coupling": {"net_ATP_to_GTP_mM": v[n["transfer"]],
                          "GTP_sinks_mM": {r: v[r] for r in n["GTP_sinks"]},
                          "GDP_sources_mM": {r: v[r] for r in n["GDP_sources"]}},
        "adenylate_kinase": {r: v[r] for r in cycles["adenylate_kinase"]},
        "PRPP": {"source_mM": v[p["source"]], "sinks_mM": {r: v[r] for r in p["sinks"]}},
        "glycolytic_yield": {"investment_mM": invest, "return_mM": ret,
                             "yield": ret/invest if invest > 0 else None},
        "rapoport_luebering": {"bypass_mM": v[rl["bypass"]], "direct_mM": v[rl["direct"]], "return_mM": v[rl["return"]],
                               "bypass_share": v[rl["bypass"]]/outflow if outflow > 0 else None}}


def first_below(time, values, level):
    """First saved time strictly below a level, or None. Support-based, not continuous."""
    time, values = np.asarray(time, float), np.asarray(values, float)
    if time.shape != values.shape or np.any(np.diff(time) <= 0):
        raise ValueError("aligned increasing support required")
    hit = np.flatnonzero(values < level)
    return float(time[hit[0]]) if hit.size else None


def reading(primary, thresholds):
    """Registered prioritization flags for the primary window. Several may hold."""
    consumers = primary["ATP_consumption_share"]
    pnc_ndpk = consumers.get("VNDPK", 0.)
    y, bypass = primary["glycolytic_yield"], primary["bypass_share"]
    gate = primary["gate"]
    flags = {
        "NDPK_purine_cycle": bool(pnc_ndpk >= thresholds["dominant_consumer_share"]),
        "PRPPASe": bool(consumers.get("VPRPPASe", 0.) >= thresholds["dominant_consumer_share"]),
        "availability_gate_on_PGK_PK": bool(sum(gate[r]["lost"] for r in ("VPGK", "VPK")) > sum(gate[r]["executed"] for r in ("VPGK", "VPK"))),
        "lower_glycolysis_supply": bool((y is not None and y < thresholds["glycolytic_yield_below"])
                                        or (bypass is not None and bypass > thresholds["bypass_share_above"]))}
    flags["none"] = not any(flags.values())
    return flags
