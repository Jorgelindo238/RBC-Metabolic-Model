"""Conditional two-phase glucose inventory constraints, not new flux measurements."""

import argparse
import json
from pathlib import Path

import numpy as np

from run_glut_only_free_replay import ROOT, observations, sha, write


def interval_constraints(time, glucose, external):
    time, glucose, external = map(lambda v: np.asarray(v, dtype=float), (time, glucose, external))
    if (time.ndim != 1 or len(time) < 2 or glucose.shape != time.shape or external.shape != time.shape
            or any(not np.all(np.isfinite(v)) for v in (time, glucose, external)) or np.any(np.diff(time) <= 0)
            or np.any(glucose < 0) or np.any(external < 0)):
        raise ValueError("aligned finite nonnegative source concentrations and ordered times required")
    lower, upper, rows = 0., 1., []
    for i in range(len(time)-1):
        dg, de = float(glucose[i+1]-glucose[i]), float(external[i+1]-external[i])
        slope = dg-de
        lo, hi = 0., 1.
        if slope > 0:
            hi = min(1., -de/slope)
        elif slope < 0:
            lo = max(0., -de/slope)
        elif de > 0:
            lo, hi = 1., 0.
        lower, upper = max(lower, lo), min(upper, hi)
        rows.append({"left_day": float(time[i]), "right_day": float(time[i+1]),
            "GLC_change_mM": dg, "EGLC_change_mM": de,
            "interval_constant_H_lower": lo, "interval_constant_H_upper": hi,
            "required_VHK_integrals_cell_mM": {str(h): -(h*dg+(1-h)*de)/h for h in (.574, .58, .632)},
            "extra_external_depletion_for_nonnegative_HK_at_H0.58_mM": max(0., de+.58/(1-.58)*dg)})
    return {"intervals": rows, "constant_H_intersection": {"lower": lower, "upper": upper,
        "nonempty": bool(lower <= upper and upper > 0 and lower < 1)},
        "scope": "exact_nominal_endpoints_constant_phase_fractions_GLC_import_and_nonnegative_HK_only",
        "assay_noise_or_variable_geometry_excluded": False,
        "source_values_modified": False,
        "interpretation": "conditional_source_consistency_diagnostic_not_experimental_reaction_flux_or_global_biological_infeasibility"}


def audit(out):
    if out.exists():
        raise ValueError("fresh observational audit directory required")
    from rbc_distinct_volume_transport import phase_matrix
    t, obs = observations()
    names, reactions, matrix, *_ = phase_matrix(.58)
    columns = {reactions[i]: float(v) for i, v in enumerate(matrix[names.index("GLC")]) if v != 0}
    if columns != {"VEGLC": 1., "VHK": -1.}:
        raise ValueError("GLC source/sink scope changed; update the derived constraint")
    report = interval_constraints(t, obs["GLC"], obs["EGLC"])
    report["source_kinetic_assumption"] = columns
    files = [Path(__file__), ROOT / "output/fla_latent_inference_preparation_2026_10_06/local_observation_inventory.csv",
             ROOT / "src/rbc_distinct_volume_transport.py", ROOT / "src/rbc_stoichiometry.py"]
    report["input_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    out.mkdir(parents=True)
    write(out / "joint_glucose_observation_audit.json", report)
    return {"constant_H_intersection": report["constant_H_intersection"],
            "negative_HK_intervals_at_H0.58": [r for r in report["intervals"] if r["required_VHK_integrals_cell_mM"]["0.58"] < 0]}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(audit(args.out.resolve()), indent=2))
