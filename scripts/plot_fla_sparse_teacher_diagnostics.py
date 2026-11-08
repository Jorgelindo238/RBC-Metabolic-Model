"""Inspect a preselected sparse training reconstruction, without fitting or replay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from equadiff_brodbar import BRODBAR_METABOLITE_MAP
from fla_teacher_resolution import TrainingCurves


def run(out):
    contract = json.loads((out / "preregistered_contract.json").read_text())
    design = contract["design"]
    seed = design["noise_seeds"][0]
    frame = pd.read_csv(out / "datasets" / f"noise_{seed}" / "observations.csv", float_precision="round_trip")
    pools = ("EGLC", "ELAC", "GLC", "LAC")
    observations = frame[list(pools)].to_numpy().T
    query = np.linspace(1., 22., 1001)
    curves = {mode: TrainingCurves(frame.time_day, observations, training_end=22., mode=mode,
                                   noise_cv=design["noise_coefficient_of_variation"]).evaluate(query) for mode in ("raw", "smooth")}
    truth = np.load(ROOT / design["parent_archive"] / "truth/evaluation.npz")
    training = truth["time"] <= 22.
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout="constrained")
    colors = {"raw": "#b45446", "smooth": "#248779"}
    for row, (external, internal, reaction) in enumerate((("EGLC", "GLC", "VEGLC"), ("ELAC", "LAC", "VELAC"))):
        for column, pool in enumerate((external, internal)):
            axis = axes[row, column]
            axis.plot(truth["time"][training], truth["states"][BRODBAR_METABOLITE_MAP[pool], training],
                      color="#30343b", linewidth=1.5, label="Known synthetic reference")
            i = pools.index(pool)
            for mode, (values, _) in curves.items():
                axis.plot(query, values[i], color=colors[mode], linewidth=1.3, linestyle="--",
                          label="Training PCHIP" if mode == "raw" else "Training log-GCV")
            axis.scatter(frame.time_day, observations[i], s=22, facecolor="white", edgecolor="#555555", zorder=5, label="Seven noisy observations")
            axis.set(title=pool, ylabel="Concentration (mM)", xlabel="Model day")
        axis = axes[row, 2]
        axis.plot(truth["time"][training], truth["effective"][row, training], color="#30343b", linewidth=1.5, label="Executed synthetic reference")
        for mode, (_, derivatives) in curves.items():
            flux = (-1. if row == 0 else 1.)*derivatives[row]
            axis.plot(query, flux, color=colors[mode], linewidth=1.3, linestyle="--", label="PCHIP teacher" if mode == "raw" else "Log-GCV teacher")
        axis.set(title=reaction, ylabel="Teacher flux (mM/day)", xlabel="Model day")
    for axis in axes.ravel():
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(alpha=.12)
        axis.set_xlim(1., 22.)
        axis.set_xticks([1, 4, 8, 11, 15, 18, 22])
    axes[0, 0].legend(fontsize=7, frameon=False, loc="best")
    axes[0, 2].legend(fontsize=7, frameon=False, loc="best")
    fig.suptitle(f"Sparse training reconstruction (preselected seed {seed}, synthetic CV 0.5%)", fontsize=12)
    for suffix in (".png", ".pdf"):
        fig.savefig(out / ("sparse_training_reconstruction"+suffix), dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "output/fla_sparse_teacher_resolution_2026_10_05")
    run(parser.parse_args().out.resolve())
