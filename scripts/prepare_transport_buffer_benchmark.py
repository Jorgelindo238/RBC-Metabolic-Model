"""Preregister recovery and execute only synthetic truth/numerical smoke tests."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_transport_buffer_synthetic import (quadrature, sensitivity, simulate, symmetry_inputs, validate_config)

CONFIG = ROOT / "config/fla_transport_buffer_synthetic.json"


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def close(a, b, config):
    return bool(np.allclose(a, b, atol=config["numerical_atol"], rtol=config["numerical_rtol"]))


def prepare(out):
    if out.exists():
        raise ValueError("use a fresh benchmark archive")
    config = validate_config(json.loads(CONFIG.read_text()))
    out.mkdir(parents=True)
    protected = [CONFIG, Path(__file__), ROOT / "src/fla_transport_buffer_synthetic.py", ROOT / "src/fla_transport_access_ph.py",
                 ROOT / "src/rbc_distinct_volume_transport.py", ROOT / "qa/test_transport_buffer_preparation.py",
                 ROOT / "output/transport_source_processing_2026_10_06/manifest.json"]
    write_json(out / "preregistered_design.json", {"design": config,
        "input_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in protected},
        "fit_status": "not_executed", "biological_replay_status": "not_executed"})
    summaries, spectra, controls = [], [], []
    replays = 0
    for scenario in config["scenarios"]:
        results = {}
        for profile in config["solver_profiles"]:
            result = simulate(config, scenario, profile=profile)
            replays += 1
            g4, g8 = [quadrature(result, config, n) for n in config["quadrature_orders"]]
            integral = float(result["states"][4, -1])
            checks = {"amount_closure": close(result["amount_residual"], 0, config),
                "acid_closure": close(result["acid_residual"], 0, config), "extent_closure": close(result["extent_state_residual"], 0, config),
                "quadrature_orders": close(g4, g8, config), "integrated_flux": close(g8, integral, config),
                "positive_concentrations": bool(min(result["states"][:2].min(), result["accepted_states"][:2].min()) >= 0)}
            if not all(checks.values()):
                raise ValueError("synthetic numerical check failed: " + str(checks))
            np.savez_compressed(out / (scenario["name"] + "_" + profile + ".npz"),
                **{key: result[key] for key in ("time", "states", "accepted_time", "accepted_states", "initial", "flux",
                                               "amount_residual", "acid_residual", "extent_state_residual")})
            summaries.append({"scenario": scenario["name"], "profile": profile, "checks": checks,
                "initial_flux": float(result["flux"][0]), "integrated_export_cell_mM": integral,
                "initial_pH": result["initial"][2:4].tolist(), "final_pH": result["states"][2:4, -1].tolist(),
                "quadrature4": g4, "quadrature8": g8})
            results[profile] = result
        if not close(results["strict"]["states"], results["ultrastrict"]["states"], config):
            raise ValueError("strict/ultrastrict divergence")
        reference = results["ultrastrict"]
        for c in config["negative_control"]["scale_factors"]:
            shifted = simulate(config, scenario, **symmetry_inputs(config, scenario, c), time=reference["time"])
            replays += 1
            concentrations_same = close(reference["states"][:2], shifted["states"][:2], config)
            phe_same = close(reference["states"][3], shifted["states"][3], config)
            phi_offset = close(shifted["states"][2] - reference["states"][2], np.log10(c), config)
            flux_same = close(reference["flux"], shifted["flux"], config)
            if not all((concentrations_same, phe_same, phi_offset, flux_same)):
                raise ValueError("exact symmetry negative control failed")
            controls.append({"scenario": scenario["name"], "scale": c, "concentrations_unchanged": concentrations_same,
                "pHe_unchanged": phe_same, "flux_unchanged": flux_same, "constant_pHi_shift": float(np.log10(c)),
                "pHi_offset_verified": phi_offset,
                "interpretation": "unknown_Km_access_i_pHi0_symmetry; pHe_alone_does_not_break_this_toy_symmetry"})
            np.savez_compressed(out / f"{scenario['name']}_symmetry_{c}.npz", time=shifted["time"], states=shifted["states"], flux=shifted["flux"])
        for schedule, time in (("sparse", np.array([t for t in config["sparse_days"] if t <= config["training_end_day"]])),
                               ("dense", np.linspace(config["horizon_day"][0], config["training_end_day"], config["dense_training_count"]))):
            jacobians = [sensitivity(config, scenario, time, step=step) for step in config["finite_difference_steps"]]
            replays += 2 * 8
            np.savez_compressed(out / f"{scenario['name']}_{schedule}_sensitivities.npz", time=time, J_step1=jacobians[0], J_step2=jacobians[1])
            scaling = config["sensitivity_scaling"]
            scales = np.array([scaling["concentration_mM"]] * 2 + [scaling["pH_units"]] * 2)
            for plan, rows in config["observation_plans"].items():
                arrays = [(j[rows] / scales[rows, None, None]).reshape(-1, 4) for j in jacobians]
                singular = np.linalg.svd(arrays[0], compute_uv=False)
                delta_norm = float(np.linalg.norm(arrays[0] - arrays[1], ord=2))
                spectra.append({"scenario": scenario["name"], "schedule": schedule, "plan": plan,
                    "training_days": time.tolist(), "scaled_singular_values": singular.tolist(),
                    "two_step_J_difference_spectral_norm": delta_norm,
                    "interpretation": "local_conditional_design_diagnostic_not_recovery_or_global_identifiability"})
    summary = {"truth_replays": summaries, "symmetry_controls": controls, "sensitivity_spectra": spectra,
        "synthetic_forward_integrations": replays, "recovery_fits_executed": 0, "biological_ODE_replays": 0,
        "kinetic_parameters_promoted": False, "source_data_used_as_synthetic_truth": False,
        "next": "bounded_staged_synthetic_recovery_using_frozen_design_not_biological_fitting"}
    write_json(out / "summary.json", summary)
    protocol = """# Preregistered MCT-buffer recovery benchmark

## Scope

Closed toy only: LAC, ELAC, pHi, pHe and integrated export. No ATP, glycolysis, AE1, CO2, gas reservoir or metabolism. Constant effective capacities are synthetic context parameters, not physiological4C estimates. This prepares a recovery experiment; no optimizer or biological RBC replay runs.

## Model and observations

Activity arguments are access_i*LAC and access_e*ELAC. The reduced reversible MCT rate is reused with explicit Km/conductance. Cell-normalized export gives dLAC=-j, dELAC=H/(1-H)*j, dpHi=j/beta_i and dpHe=-H/(1-H)*j/beta_e. Amount and acid-equivalent invariants are checked against an integrated-extent state and accepted-step quadrature. There is no clamped pH reservoir in this toy and no independent derivative clipping.

Use original JBC4C TIMES only, with training through source day7.0417 and later days reserved for holdout. Also use a dense synthetic training design. Do not transfer the JBC day origin to Bordbar or interpret simulated values as measured JBC data. Observation plans include concentrations alone, plus pHe, and plus both pHi/pHe. Initial pHi is an unknown only in the declared recovery scope; known initial concentration values remain fixed. pH22 is not a second independent pH measurement. Design scaling and future noise levels are not source covariance estimates.

## Exact negative control

With constant capacities and no additional pH-dependent processes, the simultaneous transformation access_i*=c, Km_i*=c, pHi0+=log10(c) preserves all concentrations, pHe and transport flux, while shifting pHi by a constant. This tests a full-rate toy symmetry, stronger than merely matching the driving-term sign. It requires allowing unknown intracellular Km and does not assert nonidentifiability for the full RBC network or the restricted known-Km benchmark. pHe alone does not remove this symmetry; independently supported intracellular pH or activity/affinity coordinates are needed. Initial pHi and all parameters must not be supplied from synthetic truth to a concentration-only fit where declared unknown.

## Recovery stages, not yet executed

1. Oracle conductance-only recovery with all other inputs known, to test implementation.
2. Conductance/beta_e recovery with independent pH observations and other inputs fixed.
3. Conditional access_i/pHi0 recovery with fixed supported Km; compare concentration-only and pH plans without pretending fixed Km is learned evidence.
4. Unknown-Km symmetry negative control. Report the equivalent parameter family instead of declaring a unique solution from one optimizer start.

Use finite bounded least-squares and multiple prespecified interior starts, at most100 evaluations/start. Parameters/accuracy/noise seeds are frozen in preregistered_design.json. Generate noise after freezing the design. Fit only training samples; calculate holdout error with uninterrupted trajectories. A concentration-derived flux teacher shares the observations and must not be counted as independent likelihood. In this closed toy, integrated lactate transfer is H/(1-H)*integral(j), not the cell-normalized flux itself. Report numerical validity, parameter recovery, holdout accuracy and multistart agreement separately. Sensitivity spectra alone do not pass recovery. Recovery tolerances are design choices, not biological endpoint criteria.

## Preparation outputs

Strict/ultrastrict truth pilots, exact-symmetry pilots and two-step local sensitivities are saved. These test the model and the proposed information content; they do not calibrate kinetic constants. The actual staged/noisy recovery campaign is the next separately reported execution. Full-RBC J1-J4 coupling remains unauthorized until the biological observation/acid-base contract is supported.
"""
    (out / "recovery_protocol.md").write_text(protocol, encoding="utf-8")
    write_json(out / "manifest.json", {"output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return verify(out)


def verify(out):
    design = json.loads((out / "preregistered_design.json").read_text())
    for name, expected in design["input_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("prepared benchmark input changed: " + name)
    for name, expected in json.loads((out / "manifest.json").read_text())["output_sha256"].items():
        if sha(out / name) != expected:
            raise ValueError("prepared benchmark output changed: " + name)
    config = validate_config(design["design"])
    for scenario in config["scenarios"]:
        for profile in config["solver_profiles"]:
            with np.load(out / f"{scenario['name']}_{profile}.npz") as a:
                h = config["geometry"]["hematocrit"]
                x, initial = a["states"], a["initial"]
                if (min(x[:2].min(), a["accepted_states"][:2].min()) < 0
                        or not close(h * x[0] + (1 - h) * x[1], h * initial[0] + (1 - h) * initial[1], config)
                        or not close(-h * config["truth"]["beta_i"] * (x[2] - initial[2])
                                     - (1 - h) * config["truth"]["beta_e"] * (x[3] - initial[3]), 0, config)
                        or a["accepted_time"][-1] != config["horizon_day"][1]):
                    raise ValueError("stored closed-toy invariants failed")
    summary = json.loads((out / "summary.json").read_text())
    if summary["recovery_fits_executed"] != 0 or summary["biological_ODE_replays"] != 0:
        raise ValueError("preparation scope changed")
    return {"verified": True, "synthetic_forward_integrations": summary["synthetic_forward_integrations"],
            "truth_cases": len(summary["truth_replays"]), "exact_symmetry_controls": len(summary["symmetry_controls"]),
            "sensitivity_designs": len(summary["sensitivity_spectra"]), "recovery_fits_executed": 0, "biological_ODE_replays": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if bool(args.out) == bool(args.verify):
        parser.error("choose exactly one of --out or --verify")
    print(json.dumps(prepare(args.out.resolve()) if args.out else verify(args.verify.resolve()), indent=2))
