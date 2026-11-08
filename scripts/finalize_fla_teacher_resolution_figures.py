"""Presentation-only exports from completed, archived synthetic results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def positive_axis(axis, values):
    values = np.asarray(values)
    if not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("error plot requires finite nonnegative scores")
    if np.all(values > 0):
        axis.set_yscale("log")
        axis.set_ylim(values.min()/1.6, values.max()*1.5)
    else:
        axis.set_yscale("symlog", linthresh=.01)
        axis.set_ylim(0., max(values.max()*1.5, .01))


def run(out):
    summary = json.loads((out / "summary.json").read_text())
    contract = json.loads((out / "preregistered_contract.json").read_text())
    design = contract["design"]
    frame = pd.DataFrame(summary["fits"])
    noisy = frame[frame.case != "clean"]
    metrics = pd.read_csv(out / "full_pool_replay_metrics.csv")
    original = out / "initial_figures"
    original.mkdir(exist_ok=True)
    for name in ("grid_smoothing_comparison", "holdout_method_comparison"):
        for suffix in (".png", ".pdf"):
            path = out / (name+suffix)
            if not (original / path.name).exists():
                shutil.copy2(path, original / path.name)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    for i, axis in enumerate(axes):
        displayed = []
        for mode, title, color in (("raw", "PCHIP", "#b45446"), ("smooth", "Log-GCV", "#248779")):
            errors = [100*np.asarray(noisy[noisy.method == f"{mode}_uniform{count}"].relative_parameter_error.tolist())[:, i]
                      for count in design["uniform_grid_counts"]]
            medians, maxima = [np.median(e) for e in errors], [np.max(e) for e in errors]
            displayed.extend(medians+maxima)
            axis.plot(design["uniform_grid_counts"], medians, marker="o", color=color, label=f"{title}: median")
            axis.plot(design["uniform_grid_counts"], maxima, linestyle=":", color=color, label=f"{title}: maximum")
        for name, title, color in (("raw_aligned8", "Aligned PCHIP", "#4d72b4"),
                                   ("smooth_aligned8", "Aligned log-GCV", "#53565c"), ("raw_integrated", "Raw intervals", "#967c24")):
            value = np.median(100*np.asarray(noisy[noisy.method == name].relative_parameter_error.tolist())[:, i])
            displayed.append(value)
            axis.axhline(value, linestyle="--", color=color, label=f"{title}: median")
        positive_axis(axis, displayed)
        axis.set_xscale("log")
        axis.set_xticks(design["uniform_grid_counts"], design["uniform_grid_counts"])
        axis.set(title=("Glucose capacity", "Lactate capacity")[i], xlabel="Uniform teacher grid points", ylabel="Absolute capacity error (%)")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(alpha=.15)
    axes[1].legend(fontsize=7, frameon=False, loc="upper right")
    fig.suptitle(f"Synthetic FLA: grid and smoothing comparison ({len(design['noise_seeds'])} paired noise seeds)", fontsize=12)
    for suffix in (".png", ".pdf"):
        fig.savefig(out / ("grid_smoothing_comparison"+suffix), dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    labels = ("Legacy 401", "Aligned PCHIP", "Aligned log-GCV", "Raw intervals")
    colors = ("#b45446", "#4d72b4", "#248779", "#967c24")
    for axis, pool in zip(axes, ("EGLC", "ELAC")):
        displayed = []
        for position, (method, color) in enumerate(zip(design["replay_methods"], colors)):
            values = metrics[metrics.label.str.startswith("noise_") & metrics.label.str.endswith("_"+method)
                             & (metrics.period == "holdout") & (metrics.name == pool)].excursion_nrmse.to_numpy()*100
            displayed.extend(values)
            axis.scatter(np.full(len(values), position), values, color=color, s=45)
        positive_axis(axis, displayed)
        axis.set_xticks(range(4), labels, fontsize=9, rotation=15, ha="right")
        axis.set(title=pool, ylabel="Holdout excursion nRMSE (%)")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", alpha=.15)
    fig.suptitle(f"Free J22-J46 predictions ({len(design['replay_noise_seeds'])} preselected noise seeds)", fontsize=12)
    for suffix in (".png", ".pdf"):
        fig.savefig(out / ("holdout_method_comparison"+suffix), dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "output/fla_teacher_resolution_2026_10_05_v2")
    run(parser.parse_args().out.resolve())
