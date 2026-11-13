"""Read sealed executed fluxes; no ODE, parameter changes or carbon tracing."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = "output/ak_pepase_2026_11_11"
CASES = {
    "control": "output/vmax_requalification_2026_11_09/controls/working_center",
    "ak_only": "output/ak_ratio_2026_11_11/candidates/balanced_forward_lowered",
    **{arm: f"{ARCHIVE}/candidates/{arm}" for arm in (
        "pepase_floor_only", "ak_balanced_pepase_intermediate", "ak_balanced_pepase_floor")},
}
# An open carbon subsystem, not a whole-network elemental conservation claim.
CARBONS = {
    **dict.fromkeys(("GLC", "G6P", "F6P", "GL6P", "GO6P", "F16BP", "EGLC"), 6),
    **dict.fromkeys(("RU5P", "R5P", "X5P", "RIB", "R1P", "PRPP"), 5),
    **dict.fromkeys(("GA3P", "DHCP", "B13PG", "P3G", "B23PG", "P2G", "PEP", "PYR", "LAC", "ELAC", "EPYR"), 3),
    "E4P": 4, "S7P": 7,
}
DAYS = (1, 4, 8, 11, 15)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(folder):
    manifest = json.loads((folder / "manifest.json").read_text())
    for relative, digest in manifest.items():
        if sha(folder / relative) != digest:
            raise ValueError(f"Archive changed: {folder / relative}")
    return len(manifest)


def amount_coefficients(names, h, carbon=False):
    if not 0 < h < 1:
        raise ValueError("hematocrit must be between zero and one")
    external = {"EGLC", "ELAC", "EPYR"}
    return np.array([(1-h if p in external else h) * (CARBONS.get(p, 0) if carbon else 1)
                     for p in names])


def integral(rates, weights, intervals, start, end):
    use = (intervals >= start-1) & (intervals < end-1)
    if not use.any():
        raise ValueError("no quadrature support")
    return rates[:, use] @ weights[use]


def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def run(out):
    if out.exists():
        raise ValueError("fresh output directory required")
    archives = {ARCHIVE, "output/ak_ratio_2026_11_11", "output/vmax_requalification_2026_11_09",
                "output/ak_pepase_decision_2026_11_11"}
    counts = {p: verify_manifest(ROOT / p) for p in archives if (ROOT / p / "manifest.json").exists()}
    receipt = json.loads((ROOT / "output/ak_pepase_decision_2026_11_11/verification.json").read_text())
    if not receipt["verified"] or receipt["archive_manifest_sha256"] != sha(ROOT / ARCHIVE / "manifest.json"):
        raise ValueError("independent receipt does not match source archive")
    design = json.loads((ROOT / ARCHIVE / "execution_design.json").read_text())
    obs = json.loads((ROOT / ARCHIVE / "observations.json").read_text())
    h = design["numeric"]["hematocrit"]
    levels, balances, boundaries, fluxes, stocks = [], [], [], [], []
    inputs = {str((ROOT/p/"manifest.json").relative_to(ROOT)): sha(ROOT/p/"manifest.json") for p in counts}
    residuals, independent_errors = [], []
    for case, base in CASES.items():
        for profile in ("strict", "ultrastrict"):
            path = ROOT/base/"joint"/profile/"flux_evidence.npz"
            inputs[path.relative_to(ROOT).as_posix()] = sha(path)
            with np.load(path) as a:
                names, reactions = a["pool_names"].tolist(), a["reactions"].tolist()
                matrix, time, states = a["matrix"], a["time"], a["states"][:len(names)]
                rates, weights, intervals = a["q8_executed_rates"], a["q8_weights"], a["q8_intervals"]
            volume = amount_coefficients(names, h)
            carbon = amount_coefficients(names, h, True)
            for r, pair in (("VEGLC", ("GLC", "EGLC")), ("VELAC", ("LAC", "ELAC"))):
                j = reactions.index(r)
                if abs(sum(volume[names.index(p)]*matrix[names.index(p), j] for p in pair)) > 1e-12:
                    raise ValueError("transport does not conserve amount at declared geometry")
            for day in DAYS:
                matches = np.flatnonzero(time == day)
                if len(matches) != 1:
                    raise ValueError("exact unique archived observation date required")
                k = matches[0]
                for pool in ("GLC", "EGLC", "LAC", "ELAC"):
                    i = names.index(pool)
                    observed = obs["values"][pool][obs["time"].index(day)]
                    levels.append(dict(case=case, profile=profile, day=day, pool=pool,
                        predicted_mM=states[i,k], observed_mM=observed,
                        phase_L_per_L_bag=volume[i], predicted_mmol_per_L_bag=volume[i]*states[i,k],
                        observed_mmol_per_L_bag=volume[i]*observed))
                for pool, c in CARBONS.items():
                    i = names.index(pool)
                    stocks.append(dict(case=case, profile=profile, day=day, pool=pool,
                        carbon_mmol_per_L_bag=carbon[i]*states[i,k], carbon_atoms=c))
            for start, end in ((1,4), (4,8), (8,11), (11,15), (1,15)):
                k0, k1 = np.searchsorted(time, [start,end])
                v = integral(rates, weights, intervals, start, end)
                use = (intervals >= start-1) & (intervals < end-1)
                # Independent summation order checks the weighted dot product.
                alternate = np.sum(rates[:,use]*weights[use], axis=1)
                independent_errors.append(float(np.max(np.abs(v-alternate))))
                prefix = dict(case=case, profile=profile, start=start, end=end)
                for pool in ("GLC", "EGLC", "LAC", "ELAC", "ATP"):
                    i = names.index(pool)
                    delta, net = volume[i]*(states[i,k1]-states[i,k0]), volume[i]*(matrix[i]@v)
                    residuals.append(float(abs(delta-net)))
                    balances.append(dict(**prefix, pool=pool, delta_mmol_per_L_bag=delta,
                        net_executed_mmol_per_L_bag=net, residual=delta-net))
                coefficients = carbon @ matrix
                delta, net = carbon @ (states[:,k1]-states[:,k0]), coefficients @ v
                residuals.append(float(abs(delta-net)))
                balances.append(dict(**prefix, pool="OPEN_CARBON_SUBSYSTEM", delta_mmol_per_L_bag=delta,
                    net_executed_mmol_per_L_bag=net, residual=delta-net))
                for j in np.flatnonzero(np.abs(coefficients)>1e-10):
                    boundaries.append(dict(**prefix, reaction=reactions[j], coefficient=coefficients[j],
                        carbon_mmol_per_L_bag=coefficients[j]*v[j]))
                for reaction in ("VEGLC", "VHK", "VPFK", "VLDH", "VELAC", "VPGK", "VPK", "VGAPDH"):
                    j = reactions.index(reaction)
                    fluxes.append(dict(**prefix, reaction=reaction, net_mM_cell_basis=v[j], net_mmol_per_L_bag=h*v[j]))
    passed = max(residuals) < 1e-5 and max(independent_errors) < 1e-10
    summary = dict(new_integrations=0, parameters_changed=False, production_promoted=False,
        source_archives_checked=counts, source_receipt_category=receipt["category"],
        hematocrit=h, hematocrit_status=design["numeric"]["hematocrit_status"],
        volume_assumption="constant phase volumes, no cell-water correction, no sampling correction",
        cases=len(CASES), profiles=2, balance_checks=len(residuals), max_amount_closure_error=max(residuals),
        max_independent_quadrature_error=max(independent_errors), passed=passed,
        carbon_origin_identifiable=False, ATP_origin_identifiable=False,
        caveats=["Open subsystem: boundary terms are not necessarily elemental leaks.",
                 "Initial B13PG/B23PG and P2G/P3G aliases preserved, not independently validated pools.",
                 "No exact fraction of lactate or ATP can be assigned to incoming glucose from these net fluxes.",
                 "Observed amount conversion is conditional on borrowed H, not matched donor validation."],
        input_sha256=inputs)
    out.mkdir(parents=True)
    for name, rows in (("levels",levels), ("balances",balances), ("carbon_boundary",boundaries),
                       ("fluxes",fluxes), ("carbon_stocks",stocks)):
        save_csv(out/f"{name}.csv", rows)
    (out/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out/"manifest.json").write_text(json.dumps({p.name:sha(p) for p in out.iterdir()}, indent=2), encoding="utf-8")
    if not passed:
        raise ValueError("audit closure failed; inspect recorded evidence")
    print(json.dumps({k:v for k,v in summary.items() if k != "input_sha256"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out.resolve())
