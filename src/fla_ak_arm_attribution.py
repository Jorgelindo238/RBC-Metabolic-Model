"""Read-only attribution of the adenylate kinase ratio arms: pure plan check and contrast.

No model, integration or filesystem access. Differences between two
trajectories are descriptive bookkeeping, not effects of single reactions.
"""

REQUIRED_FALSE = ("parameters_changed", "optimization_executed", "production_promotion_allowed", "J46_replayed")
FIELDS = ("net", "production", "consumption")


def check_plan(plan):
    if plan["new_integrations"] != 0 or any(plan[k] for k in REQUIRED_FALSE):
        raise ValueError("attribution is read-only bookkeeping")
    cases = plan["cases"]
    if plan["control_case"] not in cases or plan["primary_case"] not in cases or plan["control_case"] == plan["primary_case"]:
        raise ValueError("distinct registered control and primary cases required")
    if len({c["backend"] for c in cases.values()}) != 1:
        raise ValueError("cases must share one backend to be contrasted")
    if not all(any(c["folder"].startswith(a+"/") for a in plan["archives"]) for c in cases.values()):
        raise ValueError("every case must lie inside a registered sealed archive")
    if plan["primary_window"] not in plan["windows"] or plan["primary_profile"] not in plan["profiles"]:
        raise ValueError("primary window or profile is not registered")
    known = set(plan["ledger_pools"]) | set(plan["lumped_pools"])
    if not set(plan["contrast_pools"]) <= known:
        raise ValueError("contrast pool has no ledger")


def contrast(arm, control):
    """Arm minus control, per reaction, of net, gross production and gross consumption.

    Both arguments map reaction -> {"net", "production", "consumption"} for
    one pool and window. Rows are sorted by decreasing absolute net change.
    """
    if set(arm) != set(control):
        raise ValueError("arm and control ledgers must cover the same reactions")
    rows = [{"reaction": r, **{"control_"+k: control[r][k] for k in FIELDS}, **{"arm_"+k: arm[r][k] for k in FIELDS},
             **{"d_"+k: arm[r][k]-control[r][k] for k in FIELDS}} for r in arm]
    return sorted(rows, key=lambda row: (-abs(row["d_net"]), row["reaction"]))
