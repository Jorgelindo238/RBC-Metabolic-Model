"""Audit pinned GEM projections and run matched, unforced J1-J4 BDF replays."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
from openpyxl import load_workbook
from scipy.integrate import solve_ivp
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_agentic_gem_correction import GEM_COMMIT, MODES, GemCorrectionRHS
from fla_balance_audit import accepted_step_quadrature, integrate_intervals
from fla_joint_calibration import JointRHS
from rbc_gem_audit import pool_mapping, project_gem
from rbc_glut_only_transport import equadiff_glut_only


GEM_ROOT = ROOT / "output/rbc_gem_network_audit_2026_10_06/github/1.3.0"
PARENT = ROOT / "output/b13pg_ak_coupled_2026_11_04"
OUT = ROOT / "output/agentic_gem_correction_2026_11_04"
WORKBOOK = ROOT / "src/Data_Bordbar_et_al_exp.xlsx"
FROZEN_IC = ROOT / "output/exploratory_energy_sensitivity_J1_J4_2026_10_06/frozen_initial_state.npz"
SOURCE = {"VH2O2": ("CAT", .5), "VXAO": ("XAO2", 1.), "VXAO2": ("XAO", 1.),
          "VEGSSG": ("GTHOXABCte", 1.)}
CUTS = np.arange(1., 5.)
TIMES = np.linspace(1., 4., 301)
ENDPOINT_POOLS = ("ATP", "ADP", "AMP", "H2O2", "O2", "GSSG", "EGSSG", "HYPX", "XAN", "URT", "EURT")


def read(path):
    return json.loads(path.read_bytes())


def write(path, data):
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write("\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_audit(rhs):
    tree = read(GEM_ROOT / "tree.json")
    entries = {row["path"]: row["sha"] for row in tree["tree"] if row["type"] == "blob"}
    require(tree["sha"] == GEM_COMMIT and (GEM_ROOT / "version.txt").read_text().strip() == "1.3.0",
            "wrong GEM pin")
    files = ("model/RBC-GEM.json", "version.txt", "data/curation/reactions_evidence.tsv",
             "data/curation/reactions_removals.tsv")
    for file in files:
        data = (GEM_ROOT / file).read_bytes()
        blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        require(blob == entries[file], f"pinned blob mismatch: {file}")
    model = read(GEM_ROOT / files[0])
    inverse = {v: k for k, v in pool_mapping(model).items()}
    metabolites = {m["id"]: m for m in model["metabolites"]}
    reactions = {r["id"]: r for r in model["reactions"]}
    result = {}
    for local, (gem, scale) in SOURCE.items():
        r = reactions[gem]
        projected, missing, omitted = project_gem(r, inverse)
        require(not missing and r["lower_bound"] == 0 < r["upper_bound"], f"invalid projection: {gem}")
        j = rhs.reactions.index(local)
        expected = np.array([scale * projected.get(p, 0.) for p in rhs.names])
        np.testing.assert_allclose(rhs.volumes * rhs.matrix[:, j], rhs.hematocrit * expected, rtol=0., atol=1e-15)
        require(rhs.rate_volumes[j] == rhs.hematocrit, f"wrong rate basis: {local}")
        residual = {}
        species = {}
        for m, coefficient in r["metabolites"].items():
            info = metabolites[m]
            formula, charge = info["formula"], info["charge"]
            parts = re.findall(r"([A-Z][a-z]?)(\d*)", formula)
            require("".join(a+b for a, b in parts) == formula, f"unparsed formula: {m}")
            species[m] = {"formula": formula, "charge": charge, "coefficient": coefficient}
            for atom, number in [*[(a, int(b or 1)) for a, b in parts], ("charge", charge)]:
                residual[atom] = residual.get(atom, 0.) + coefficient * number
        require(not any(residual.values()), f"GEM elemental or charge imbalance: {gem}")
        result[local] = {"gem_id": gem, "gpr": r["gene_reaction_rule"], "species": species,
                         "full_source_atom_charge_residual": residual, "source_rate_scale": scale,
                         "omitted_source_currency": omitted, "reduced_column": dict(zip(
                             [p for p in rhs.names if p in projected], expected[expected != 0].tolist())),
                         "phase_concentration_column": {p: float(v) for p, v in zip(rhs.names, rhs.matrix[:, j]) if v},
                         "bag_amount_column": {p: float(v) for p, v in zip(rhs.names, rhs.volumes * rhs.matrix[:, j]) if v}}
    deferred = {}
    for gem in ("URATEABCte", "ACITL", "ARGN", "ARGSL"):
        r = reactions[gem]
        projected, missing, omitted = project_gem(r, inverse)
        deferred[gem] = {"gpr": r["gene_reaction_rule"], "reduced_column": projected,
                         "unmapped": missing, "omitted": omitted, "bounds": [r["lower_bound"], r["upper_bound"]]}
    return {"gem_commit": GEM_COMMIT, "verified_git_blobs": {f: entries[f] for f in files},
            "model_sha256": sha(GEM_ROOT / files[0]), "executed_projections": result, "deferred": deferred}


def verify_initial(initial, names):
    observations = read(PARENT / "observations.json")
    workbook = load_workbook(WORKBOOK, read_only=True)
    try:
        rows = list(workbook["Sheet1"].iter_rows(values_only=True))
    finally:
        workbook.close()
    panel = {r[0]: list(r[1:15]) for r in rows[1:] if r[0] in observations["values"]}
    require(list(rows[0][1:15]) == observations["time"] and panel == observations["values"],
            "archived observations differ from Sheet1")
    require(len(panel) == 55 and all(initial[names.index(p)] == values[0] for p, values in panel.items()),
            "exact55 J1 mismatch")
    with np.load(FROZEN_IC) as frozen:
        require(initial.tobytes() == frozen["states"].tobytes(), "114-coordinate initial vector changed")
    return len(panel) * len(observations["time"])


def parity(rhs, other, sol):
    maxima = np.zeros(4)
    for t, x in zip(TIMES[::10], sol.sol(TIMES[::10]).T):
        raw, executed, factors = rhs.rates(t, x)
        d = rhs(t, x)
        expected = np.ones_like(raw)
        availability = np.clip(x[:len(rhs.names)] / rhs.threshold, 0., 1.)
        for j, v in enumerate(raw):
            consumers = rhs.matrix[:, j] * v < 0.
            if np.any(consumers):
                expected[j] = availability[consumers].min()
        np.testing.assert_array_equal(factors, expected)
        np.testing.assert_array_equal(executed, raw * expected)
        np.testing.assert_allclose(d, np.r_[rhs.matrix @ executed, 0.], rtol=1e-12, atol=1e-12)
        if rhs.mode == "native":
            if rhs.backend == "joint":
                native = JointRHS(rhs.parameters, rhs.kinetics, hematocrit=rhs.hematocrit, threshold=rhs.threshold)
                reference, reference_rates = native(t, x), native.rates(t, x)
            else:
                audit = {}
                reference = equadiff_glut_only(t, x, custom_params=rhs.parameters, glucose_kinetics=rhs.kinetics,
                    hematocrit=rhs.hematocrit, reaction_availability_threshold=rhs.threshold, numerical_audit=audit)
                reference_rates = tuple(np.array([audit[k][r] for r in rhs.reactions])
                                        for k in ("raw_fluxes", "effective_fluxes", "availability_factors"))
            require(all(a.tobytes() == b.tobytes() for a, b in
                        zip((d, raw, executed, factors), (reference, *reference_rates))), "native rollback mismatch")
        for i, (a, b) in enumerate(zip((raw, executed, factors, d), (*other.rates(t, x), other(t, x)))):
            np.testing.assert_allclose(a, b, atol=1e-10, rtol=1e-12)
            maxima[i] = max(maxima[i], np.max(np.abs(a - b)))
    return dict(zip(("raw", "executed", "factors", "rhs"), maxima.tolist()))


def replay(out, rhs, other, profile, options, initial):
    label = f"{rhs.mode}_{rhs.backend}_{profile}"
    sol = solve_ivp(rhs, (CUTS[0], CUTS[-1]), initial, method="BDF", dense_output=True,
                    jac_sparsity=rhs.jacobian_sparsity, **options)
    require(sol.success and sol.t[-1] == CUTS[-1] and sol.y[:, 0].tobytes() == initial.tobytes(), label)
    states = sol.sol(TIMES)
    minimum = min(float(states[:-1].min()), float(sol.y[:-1].min()))
    intervals = []
    for order in (2, 4):
        grid = accepted_step_quadrature(sol.t, CUTS, order=order)
        points = sol.sol(grid.nodes)
        minimum = min(minimum, float(points[:-1].min()))
        raw, executed, _ = map(np.asarray, zip(*(rhs.rates(t, x) for t, x in zip(grid.nodes, points.T))))
        intervals.append((integrate_intervals(raw.T, grid), integrate_intervals(executed.T, grid)))
    for a, b in zip(*intervals):
        np.testing.assert_allclose(a, b, rtol=.001, atol=1e-6)
    daily_raw, daily_executed = intervals[-1]
    increments = np.diff(sol.sol(CUTS)[:-1], axis=1)
    phase_balance = rhs.matrix @ daily_executed
    amount_matrix = rhs.volumes[:, None] * rhs.matrix / rhs.rate_volumes[None, :]
    amount_balance = amount_matrix @ (rhs.rate_volumes[:, None] * daily_executed)
    np.testing.assert_allclose(increments, phase_balance, atol=1e-6, rtol=.001)
    np.testing.assert_allclose(increments * rhs.volumes[:, None], amount_balance, atol=1e-6, rtol=.001)
    require(minimum >= -1e-10 and np.all(states[-1] == initial[-1]), f"negative state or pH drift: {label}")
    parity_max = parity(rhs, other, sol)
    np.savez_compressed(out / f"{label}.npz", times=TIMES, states=states, accepted_time=sol.t, accepted_states=sol.y,
                        daily_raw=daily_raw, daily_executed=daily_executed, daily_increments=increments,
                        matrix=rhs.matrix, pool_volumes=rhs.volumes, rate_volumes=rhs.rate_volumes,
                        names=rhs.names, reactions=rhs.reactions)
    print(f"{label}: {sol.t.size - 1} accepted steps; ATP J4={states[rhs.names.index('ATP'), -1]:.9g}", flush=True)
    summary = {"accepted_steps": sol.t.size - 1, "nfev": sol.nfev, "minimum_mM": minimum,
               "endpoint": {p: float(states[rhs.names.index(p), -1]) for p in ENDPOINT_POOLS},
               "J1_J4_executed_cell_mM": {r: float(daily_executed[rhs.reactions.index(r)].sum())
                                          for r in (*SOURCE, "VEURT", "VOPLAH")},
               "max_daily_phase_residual_mM": float(np.max(np.abs(increments - phase_balance))),
               "max_daily_bag_residual_mM": float(np.max(np.abs(increments * rhs.volumes[:, None] - amount_balance))),
               "same_state_fast_full_max_difference": parity_max}
    return summary, (states, daily_raw, daily_executed)


def run():
    design = read(PARENT / "execution_design.json")
    case = design["cases"]["baseline"]
    initial = np.asarray(design["initial"])
    numeric = design["numeric"]
    options = {"hematocrit": numeric["hematocrit"], "threshold": numeric["availability_threshold_mM"]}
    rhs = {(mode, backend): GemCorrectionRHS(case["parameters"], case["glucose_kinetics"], mode=mode,
           backend=backend, **options) for mode in MODES for backend in ("joint", "full")}
    projection = source_audit(rhs["redox_gssg_abc", "joint"])
    cells = verify_initial(initial, rhs["native", "joint"].names)
    sources = [Path(__file__), WORKBOOK, FROZEN_IC, PARENT / "execution_design.json", PARENT / "observations.json",
               GEM_ROOT / "tree.json", *(GEM_ROOT / f for f in projection["verified_git_blobs"])]
    sources.extend(ROOT / f for f in ("src/fla_agentic_gem_correction.py", "src/equadiff_brodbar.py",
        "src/rbc_stoichiometry.py", "src/fla_joint_calibration.py", "src/rbc_glut_only_transport.py",
        "src/rbc_distinct_volume_transport.py", "src/reaction_positivity.py", "src/rbc_gem_audit.py",
        "src/rbc_gem_network.py", "src/rbc_coverage_extensions.py", "src/fla_balance_audit.py",
        "RBC/Rxn_RBC.txt", "tasks/fla_current_tasks.md", "manuscript.md"))
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    profiles = numeric["numerical_profiles"]
    OUT.mkdir(exist_ok=False)
    write(OUT / "source_projection.json", projection)
    write(OUT / "fixed_inputs.json", {"parent": PARENT.relative_to(ROOT).as_posix(), "case": case,
          "initial": initial.tolist(), "geometry_and_limiter": options, "profiles": profiles,
          "exact_source_cells": cells, "input_sha256": hashes})
    results, series = {}, {}
    for mode in MODES:
        # Both profiles on both backends for the actual matched campaign pair.
        backends = ("joint", "full") if mode in ("native", "redox_gssg_abc") else ("joint",)
        for backend in backends:
            other = "full" if backend == "joint" else "joint"
            for profile, tolerances in profiles.items():
                key = (mode, backend, profile)
                results["/".join(key)], series[key] = replay(OUT, rhs[mode, backend], rhs[mode, other],
                                                             profile, tolerances, initial)
    comparisons = {}
    for mode, backend, profile in series:
        if profile == "strict":
            keys = ((mode, backend, profile), (mode, backend, "ultrastrict"))
            comparisons["/".join((mode, backend, "strict_vs_ultrastrict"))] = compare_series(series, keys)
        if backend == "full":
            keys = ((mode, "joint", profile), (mode, backend, profile))
            comparisons["/".join((mode, profile, "joint_vs_full"))] = compare_series(series, keys)
    write(OUT / "summary.json", {"replays": results, "comparisons": comparisons,
          "fixed_Km_and_Vmax": True, "optimization_run": False, "biological_validation": False})
    write(OUT / "manifest.json", {p.name: sha(p) for p in sorted(OUT.iterdir())})
    verify()


def compare_series(series, keys):
    pairs = list(zip(*(series[k] for k in keys)))
    for a, b in pairs:
        np.testing.assert_allclose(a, b, atol=1e-5, rtol=.01)
    return {"checks": sum(a.size for a, _ in pairs), "max_absolute_difference": [
            float(np.max(np.abs(a - b))) for a, b in pairs]}


def verify():
    for file, digest in read(OUT / "manifest.json").items():
        require(sha(OUT / file) == digest, f"output hash mismatch: {file}")
    inputs = read(OUT / "fixed_inputs.json")
    for file, digest in inputs["input_sha256"].items():
        require(sha(ROOT / file) == digest, f"protected input changed: {file}")
    count = 0
    for archive in sorted(OUT.glob("*.npz")):
        with np.load(archive) as a:
            np.testing.assert_array_equal(a["accepted_states"][:, 0], inputs["initial"])
            concentrations = a["states"][:-1, ::100]
            phase_change = np.diff(concentrations, axis=1)
            np.testing.assert_allclose(phase_change, a["daily_increments"], rtol=0., atol=1e-15)
            volume = a["pool_volumes"][:, None]
            np.testing.assert_allclose(volume * phase_change,
                (volume * a["matrix"]) @ a["daily_executed"], rtol=.001, atol=1e-6)
            count += phase_change.size
    require(count == 12 * 3 * 113, "missing replay balances")
    print(f"Verified hashes and {count} saved daily pool amount balances.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    with threadpool_limits(limits=1):
        verify() if parser.parse_args().verify else run()
