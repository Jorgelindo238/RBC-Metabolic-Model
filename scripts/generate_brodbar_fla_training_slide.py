"""Generate a PowerPoint-ready FLA training math slide for Brodbar EGLC/ELAC."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
OUT_DIR = ROOT / "output" / "fla_powerpoint"
DATA_PATH = SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"

for path in (str(ROOT), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _load_brodbar_pair() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    df = pd.read_excel(DATA_PATH, sheet_name="Sheet1")
    time_cols = [col for col in df.columns if col != "Conc / mM"]
    time = np.asarray([float(col) for col in time_cols], dtype=float)
    curves = {}
    for name in ("EGLC", "ELAC"):
        row = df[df["Conc / mM"].astype(str).str.upper() == name]
        if row.empty:
            raise KeyError(f"{name} not found in {DATA_PATH}")
        curves[name] = row.iloc[0, 1:].to_numpy(dtype=float)
    return time, curves


def _teacher_flux(time: np.ndarray, values: np.ndarray, sign: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dense_time = np.linspace(float(time[0]), float(time[-1]), 250)
    pchip = PchipInterpolator(time, values)
    dense_values = pchip(dense_time)
    dense_flux = sign * pchip.derivative()(dense_time)
    return dense_time, dense_values, dense_flux


def generate_slide() -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    time, curves = _load_brodbar_pair()
    eglc_t, eglc_curve, veglc_flux = _teacher_flux(time, curves["EGLC"], -1.0)
    elac_t, elac_curve, velac_flux = _teacher_flux(time, curves["ELAC"], 1.0)

    png_path = OUT_DIR / "brodbar_fla_training_math_eglc_elac.png"
    pdf_path = OUT_DIR / "brodbar_fla_training_math_eglc_elac.pdf"

    fig = plt.figure(figsize=(16, 9), facecolor="#f8fafc")
    gs = fig.add_gridspec(
        3,
        3,
        width_ratios=[1.0, 1.18, 1.18],
        height_ratios=[0.24, 1.0, 0.64],
        left=0.035,
        right=0.975,
        top=0.94,
        bottom=0.065,
        wspace=0.20,
        hspace=0.24,
    )

    title_ax = fig.add_subplot(gs[0, :])
    title_ax.axis("off")
    title_ax.text(
        0.0,
        0.78,
        "Flux Learning Analysis (FLA) - donnees Brodbar pour entrainer le modele ODE",
        fontsize=25,
        fontweight="bold",
        color="#0f172a",
        va="center",
    )
    title_ax.text(
        0.0,
        0.23,
        "Exemple: glucose extracellulaire (EGLC) et lactate extracellulaire (ELAC)",
        fontsize=15,
        color="#334155",
        va="center",
    )

    ax_data = fig.add_subplot(gs[1, 0])
    ax_flux = fig.add_subplot(gs[1, 1])
    ax_ode = fig.add_subplot(gs[1, 2])
    ax_loss = fig.add_subplot(gs[2, :])

    for ax in (ax_data, ax_flux):
        ax.grid(True, alpha=0.25)
        ax.tick_params(labelsize=9)
        ax.set_xlabel("Temps de stockage (jours)", fontsize=10)

    ax_data.plot(eglc_t, eglc_curve, color="#2563eb", linewidth=2.2, label="EGLC PCHIP")
    ax_data.scatter(time, curves["EGLC"], color="#172554", s=28, zorder=3)
    ax_data.plot(elac_t, elac_curve, color="#059669", linewidth=2.2, label="ELAC PCHIP")
    ax_data.scatter(time, curves["ELAC"], color="#064e3b", s=28, zorder=3)
    ax_data.set_title("1. Donnees experimentales", fontsize=14, fontweight="bold", color="#0f172a")
    ax_data.set_ylabel("Concentration (mM)", fontsize=10)
    ax_data.legend(frameon=False, fontsize=9, loc="best")

    ax_flux.plot(eglc_t, veglc_flux, color="#dc2626", linewidth=2.3, label=r"$v_{EGLC}^{exp}=-d\widehat{EGLC}/dt$")
    ax_flux.plot(elac_t, velac_flux, color="#ea580c", linewidth=2.3, label=r"$v_{ELAC}^{exp}=d\widehat{ELAC}/dt$")
    ax_flux.axhline(0, color="#64748b", linewidth=0.8, linestyle="--")
    ax_flux.set_title("2. Flux experimentaux recuperes", fontsize=14, fontweight="bold", color="#0f172a")
    ax_flux.set_ylabel("Flux (mM/jour)", fontsize=10)
    ax_flux.legend(frameon=False, fontsize=9, loc="best")

    ax_ode.axis("off")
    ax_ode.set_title("3. Insertion dans l'ODE", fontsize=14, fontweight="bold", color="#0f172a", pad=14)
    ode_text = (
        r"$\frac{d\,EGLC}{dt}=-V_{EGLC}(x,\theta)$" "\n"
        r"$\frac{d\,ELAC}{dt}= V_{ELAC}(x,\theta)$" "\n\n"
        r"$V_{EGLC}(x,\theta)$ et $V_{ELAC}(x,\theta)$" "\n"
        "sont les flux ODE calcules par\n"
        "les transporteurs membranaires."
    )
    ax_ode.text(
        0.03,
        0.88,
        ode_text,
        fontsize=16,
        color="#111827",
        va="top",
        linespacing=1.35,
    )
    ax_ode.text(
        0.03,
        0.22,
        "Les parametres appris sont reinjectes:\n"
        r"$\theta^*=\{V_{max}, K_m, ...\}$" "\n"
        r"$\Rightarrow$ prochaine simulation ODE",
        fontsize=14,
        color="#334155",
        va="top",
        linespacing=1.35,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#e0f2fe", edgecolor="#0284c7", linewidth=1.3),
    )

    ax_loss.axis("off")
    ax_loss.set_facecolor("#ffffff")
    for spine in ax_loss.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor("#cbd5e1")
        spine.set_linewidth(1.2)
    loss_text_left = (
        "4. Training FLA: on ajuste les constantes cinetiques pour aligner les flux ODE sur les flux experimentaux"
    )
    ax_loss.text(0.015, 0.82, loss_text_left, fontsize=15, fontweight="bold", color="#0f172a", va="center")
    ax_loss.text(
        0.015,
        0.43,
        r"$\theta^*=\arg\min_{\theta}\left["
        r"\lambda_C\,\mathcal{L}_{conc}(\theta)"
        r"+\lambda_F\left("
        r"\|V_{EGLC}^{ODE}(t,\theta)-v_{EGLC}^{exp}(t)\|_2^2"
        r"+\|V_{ELAC}^{ODE}(t,\theta)-v_{ELAC}^{exp}(t)\|_2^2"
        r"\right)"
        r"+\mathcal{G}_{physio}(\theta)\right]$",
        fontsize=16,
        color="#111827",
        va="center",
    )
    ax_loss.text(
        0.015,
        0.13,
        "Interpretation: les points Brodbar donnent les pentes experimentales; ces pentes deviennent des flux teacher.\n"
        "La calibration apprend les constantes cinetiques qui reproduisent ces flux, puis les reinjecte dans l'ODE.",
        fontsize=12.0,
        color="#475569",
        va="center",
    )

    fig.savefig(png_path, dpi=220)
    fig.savefig(pdf_path)
    plt.close(fig)

    return {"png": str(png_path), "pdf": str(pdf_path)}


if __name__ == "__main__":
    paths = generate_slide()
    print(paths)
