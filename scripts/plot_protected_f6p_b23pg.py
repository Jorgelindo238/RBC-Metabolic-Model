"""Presentation-only successor: shared contribution scales and sparse ticks."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

from run_glut_only_free_replay import sha, write

ROOT = Path(__file__).resolve().parents[1]


def plot(archive, out):
    if out.exists():
        raise ValueError("fresh figure directory required")
    contract = json.loads((archive/"execution_contract.json").read_text())
    parent = ROOT/contract["config"]["parent_archive"]
    f = json.loads((parent/"execution_design.json").read_text())
    obs = json.loads((parent/"observations.json").read_text())
    with (archive/"reaction_deltas.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    paths = {"control": ROOT/f["parent_design"]["source_archive"]/"J1_J10/glut_real_candidate_ultrastrict/replay.npz",
        "protected": parent/"audits"/(contract["parent_selected_label"]+"_J10")/"J1_J10/glut_real_candidate_ultrastrict/replay.npz"}
    series = {}
    for case, path in paths.items():
        with np.load(path) as z:
            series[case] = (z["time"].copy(), z["states"].copy(), z["pool_names"].tolist())
    fig, axes = plt.subplots(3, 3, figsize=(15, 10), constrained_layout=True)
    for row, pool in enumerate(("F6P", "B23PG", "PEP")):
        ax = axes[row, 0]
        for case, color, style in (("control", "#247888", "--"), ("protected", "#b44468", "-")):
            time, states, names = series[case]
            ax.plot(time, states[names.index(pool)], color=color, linestyle=style,
                    label="GLUT-only control" if case == "control" else "Protected candidate")
        times = [1., 4., 8.]
        ax.scatter(times, [obs["values"][pool][obs["time"].index(t)] for t in times],
                   color="#242424", marker="D", s=24, zorder=4, label="Nominal source")
        ax.set(title=pool, xlabel="Model day", ylabel="Concentration (mM)", xlim=(1, 10))
        ax.legend(fontsize=8)
        members = [r for r in rows if r["pool"] == pool and r["window"] in ("J1_J4", "J4_J8")]
        values = [float(r["executed_mM_delta"]) for r in members]+[0.]
        left, right = min(values), max(values)
        span = max(right-left, 1e-6)
        for col, window in enumerate(("J1_J4", "J4_J8"), 1):
            selected = [r for r in members if r["window"] == window]
            vals = [float(r["executed_mM_delta"]) for r in selected]
            ax = axes[row, col]
            bars = ax.barh([r["reaction"] for r in selected], vals,
                           color=["#b44468" if v > 0 else "#247888" for v in vals])
            ax.bar_label(bars, labels=[f"{v:+.4f}" for v in vals], padding=4, fontsize=8)
            ax.axvline(0, color="#242424", linewidth=.7)
            ax.set(title=window.replace("_", "-"), xlim=(left-.22*span, right+.22*span),
                   xlabel="Signed executed contribution change\n(protected - control, mM)")
            ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
    fig.suptitle("Executed-flux attribution at fixed parameter sets", fontsize=14)
    out.mkdir(parents=True)
    fig.savefig(out/"f6p_b23pg_pep_attribution_readable.png", dpi=170)
    plt.close(fig)
    sources = [Path(__file__), archive/"manifest.json", archive/"execution_contract.json", archive/"reaction_deltas.csv",
               parent/"execution_design.json", parent/"observations.json", *paths.values()]
    write(out/"manifest.json", {"purpose": "presentation_only_same_reviewed_numbers_shared_scales",
        "input_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in sources},
        "output_sha256": {p.name: sha(p) for p in out.iterdir() if p.is_file()}})
    return {"figure_created": True, "scientific_archive_modified": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(plot(args.archive.resolve(), args.out.resolve()), indent=2))
