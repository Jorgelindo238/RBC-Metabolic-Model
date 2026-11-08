"""Plot Michel standardized data against the current best kinetic ODE params."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_MICHEL_CSV = ROOT / "tests" / "donnees_michel_standardized.csv"
DEFAULT_PARAMS = ROOT / "Simulations" / "brodbar" / "calibration" / "best_params.json"
DEFAULT_OUT_DIR = ROOT / "output" / "michel_best_params_simulation"

for path in (str(ROOT), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def _load_standardized_csv(path: Path) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
    df = pd.read_csv(path)
    if "Metabolite" not in df.columns:
        raise ValueError(f"Expected a Metabolite column in {path}")
    time_cols = [col for col in df.columns if col != "Metabolite"]
    time = np.asarray([float(col) for col in time_cols], dtype=float)
    curves: dict[str, np.ndarray] = {}
    order: list[str] = []
    for _, row in df.iterrows():
        name = str(row["Metabolite"]).strip().upper()
        if not name:
            continue
        values = np.asarray([float(row[col]) for col in time_cols], dtype=float)
        if not np.all(np.isfinite(values)):
            continue
        curves[name] = values
        order.append(name)
    return time, curves, order


def _load_params(path: Path) -> dict[str, float]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        str(name): float(value)
        for name, value in payload.items()
        if isinstance(value, (int, float))
    }


def _seed_initial_conditions(
    *,
    curves: Mapping[str, np.ndarray],
    seed_with_michel: bool,
) -> tuple[np.ndarray, list[str]]:
    x0 = np.asarray(load_initial_conditions(), dtype=float)
    seeded: list[str] = []
    if not seed_with_michel:
        return x0, seeded
    for name, values in curves.items():
        idx = BRODBAR_METABOLITE_MAP.get(name)
        if idx is None or idx >= x0.size:
            continue
        x0[int(idx)] = max(float(values[0]), 0.0)
        seeded.append(name)
    return x0, seeded


def _simulate(
    *,
    time_exp: np.ndarray,
    curves: Mapping[str, np.ndarray],
    params: Mapping[str, float],
    seed_with_michel: bool,
    dense_points: int,
    method: str,
    rtol: float,
    atol: float,
) -> tuple[Any, np.ndarray, list[str]]:
    x0, seeded = _seed_initial_conditions(curves=curves, seed_with_michel=seed_with_michel)
    t0 = float(time_exp[0])
    tmax = float(time_exp[-1])
    t_dense = np.linspace(t0, tmax, int(dense_points))
    t_eval = np.unique(np.concatenate([t_dense, time_exp]))
    sol = solve_ivp(
        lambda t, y: equadiff_brodbar(
            t,
            y,
            custom_params=dict(params),
            curve_fit_strength=0.0,
        ),
        (t0, tmax),
        x0,
        method=method,
        t_eval=t_eval,
        rtol=float(rtol),
        atol=float(atol),
    )
    if not sol.success:
        raise RuntimeError(f"ODE solve failed: {sol.message}")
    sol.y[:] = np.maximum(sol.y, 0.0)
    return sol, t_eval, seeded


def _extract_sim_curves(sol: Any, names: Sequence[str]) -> dict[str, np.ndarray]:
    out = {}
    for name in names:
        idx = BRODBAR_METABOLITE_MAP.get(name)
        if idx is None or int(idx) >= sol.y.shape[0]:
            continue
        out[name] = np.asarray(sol.y[int(idx), :], dtype=float)
    return out


def _interp_sim_at_exp(sol: Any, sim_curves: Mapping[str, np.ndarray], time_exp: np.ndarray) -> dict[str, np.ndarray]:
    return {
        name: np.interp(time_exp, np.asarray(sol.t, dtype=float), values)
        for name, values in sim_curves.items()
    }


def _metrics(curves: Mapping[str, np.ndarray], sim_at_exp: Mapping[str, np.ndarray]) -> list[dict[str, float | str]]:
    rows = []
    for name, exp_values in curves.items():
        sim_values = sim_at_exp.get(name)
        if sim_values is None:
            continue
        rmse = float(np.sqrt(np.mean((sim_values - exp_values) ** 2)))
        norm = float(max(np.mean(np.abs(exp_values)), 0.01))
        nrmse = float(rmse / norm)
        endpoint_error = float(abs(sim_values[-1] - exp_values[-1]) / max(abs(float(exp_values[-1])), 0.01))
        rows.append(
            {
                "metabolite": name,
                "rmse": rmse,
                "nrmse": nrmse,
                "endpoint_error": endpoint_error,
                "exp_final": float(exp_values[-1]),
                "sim_final": float(sim_values[-1]),
            }
        )
    return sorted(rows, key=lambda row: float(row["nrmse"]), reverse=True)


def _plot_pages(
    *,
    sol: Any,
    curves: Mapping[str, np.ndarray],
    order: Sequence[str],
    sim_curves: Mapping[str, np.ndarray],
    time_exp: np.ndarray,
    metrics_rows: Sequence[Mapping[str, Any]],
    out_dir: Path,
    prefix: str,
    per_page: int = 12,
) -> dict[str, Any]:
    metric_by_name = {row["metabolite"]: row for row in metrics_rows}
    pdf_path = out_dir / f"{prefix}_simulation_vs_michel.pdf"
    png_paths: list[str] = []
    names = [name for name in order if name in curves and name in sim_curves]
    page_count = int(math.ceil(len(names) / per_page))

    with PdfPages(pdf_path) as pdf:
        for page_idx in range(page_count):
            page_names = names[page_idx * per_page : (page_idx + 1) * per_page]
            fig, axes = plt.subplots(4, 3, figsize=(15, 11), constrained_layout=True)
            axes_flat = axes.flatten()
            for ax, name in zip(axes_flat, page_names):
                exp_values = curves[name]
                sim_values = sim_curves[name]
                row = metric_by_name.get(name, {})
                ax.plot(sol.t, sim_values, color="#2563eb", linewidth=2.0, label="ODE best params")
                ax.scatter(time_exp, exp_values, color="#111827", s=24, zorder=3, label="Michel")
                ax.set_title(
                    f"{name}  nRMSE={float(row.get('nrmse', 0.0)):.2f}",
                    fontsize=10,
                    fontweight="bold",
                )
                ax.set_xlabel("Time (days)", fontsize=8)
                ax.set_ylabel("mM", fontsize=8)
                ax.grid(True, alpha=0.25)
                ax.tick_params(labelsize=8)
            for ax in axes_flat[len(page_names) :]:
                ax.axis("off")
            handles, labels = axes_flat[0].get_legend_handles_labels()
            fig.legend(handles, labels, loc="upper right", frameon=False, fontsize=9)
            fig.suptitle(
                f"Michel data vs ODE simulation with current best kinetic constants ({page_idx + 1}/{page_count})",
                fontsize=14,
            )
            pdf.savefig(fig)
            png_path = out_dir / f"{prefix}_simulation_vs_michel_page_{page_idx + 1:02d}.png"
            fig.savefig(png_path, dpi=180)
            png_paths.append(str(png_path))
            plt.close(fig)

    return {
        "pdf": str(pdf_path),
        "png_pages": png_paths,
        "metabolite_count": len(names),
        "page_count": page_count,
    }


def _plot_summary(
    *,
    metrics_rows: Sequence[Mapping[str, Any]],
    out_dir: Path,
    prefix: str,
    top_n: int = 18,
) -> str:
    rows = list(metrics_rows[:top_n])
    names = [str(row["metabolite"]) for row in rows][::-1]
    values = [float(row["nrmse"]) for row in rows][::-1]
    fig, ax = plt.subplots(figsize=(12, 8), constrained_layout=True)
    colors = ["#dc2626" if value > 1.0 else "#2563eb" for value in values]
    ax.barh(names, values, color=colors)
    ax.axvline(1.0, color="#64748b", linestyle="--", linewidth=1.0)
    ax.set_xlabel("nRMSE vs Michel")
    ax.set_title("Worst-fitting Michel metabolites under current best kinetic constants", fontweight="bold")
    ax.grid(axis="x", alpha=0.25)
    png_path = out_dir / f"{prefix}_worst_nrmse_summary.png"
    fig.savefig(png_path, dpi=180)
    plt.close(fig)
    return str(png_path)


def run_plot(
    *,
    michel_csv: Path = DEFAULT_MICHEL_CSV,
    params_path: Path = DEFAULT_PARAMS,
    out_dir: Path = DEFAULT_OUT_DIR,
    seed_with_michel: bool = True,
    dense_points: int = 240,
    method: str = "LSODA",
    rtol: float = 1e-5,
    atol: float = 1e-7,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    time_exp, curves, order = _load_standardized_csv(Path(michel_csv))
    params = _load_params(Path(params_path))
    sol, _t_eval, seeded = _simulate(
        time_exp=time_exp,
        curves=curves,
        params=params,
        seed_with_michel=seed_with_michel,
        dense_points=dense_points,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    sim_curves = _extract_sim_curves(sol, order)
    sim_at_exp = _interp_sim_at_exp(sol, sim_curves, time_exp)
    metrics_rows = _metrics(curves, sim_at_exp)

    prediction_rows = []
    for name in order:
        if name not in sim_at_exp:
            continue
        for t, exp_value, sim_value in zip(time_exp, curves[name], sim_at_exp[name]):
            prediction_rows.append(
                {
                    "metabolite": name,
                    "time_day": float(t),
                    "michel_exp": float(exp_value),
                    "ode_sim_best_params": float(sim_value),
                }
            )
    predictions_csv = out_dir / "michel_vs_best_params_predictions.csv"
    pd.DataFrame(prediction_rows).to_csv(predictions_csv, index=False)
    metrics_csv = out_dir / "michel_vs_best_params_metrics.csv"
    pd.DataFrame(metrics_rows).to_csv(metrics_csv, index=False)

    pages = _plot_pages(
        sol=sol,
        curves=curves,
        order=order,
        sim_curves=sim_curves,
        time_exp=time_exp,
        metrics_rows=metrics_rows,
        out_dir=out_dir,
        prefix="michel_best_params",
    )
    summary_png = _plot_summary(metrics_rows=metrics_rows, out_dir=out_dir, prefix="michel_best_params")

    manifest = {
        "contract_type": "michel_best_params_simulation_comparison",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "michel_csv": str(michel_csv),
        "params_path": str(params_path),
        "out_dir": str(out_dir),
        "seed_with_michel_initial_values": bool(seed_with_michel),
        "seeded_metabolites": seeded,
        "solver": {
            "method": method,
            "rtol": float(rtol),
            "atol": float(atol),
            "t_start": float(time_exp[0]),
            "t_end": float(time_exp[-1]),
            "dense_points": int(dense_points),
        },
        "mapped_metabolites": list(sim_curves.keys()),
        "metrics_csv": str(metrics_csv),
        "predictions_csv": str(predictions_csv),
        "plots": pages,
        "summary_png": summary_png,
        "worst_metabolites": metrics_rows[:10],
    }
    manifest_path = out_dir / "manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(_jsonable(manifest), indent=2), encoding="utf-8")
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot Michel data vs current best ODE kinetic params")
    parser.add_argument("--michel-csv", type=Path, default=DEFAULT_MICHEL_CSV)
    parser.add_argument("--params", type=Path, default=DEFAULT_PARAMS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--no-michel-seed", action="store_true")
    parser.add_argument("--dense-points", type=int, default=240)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=1e-5)
    parser.add_argument("--atol", type=float, default=1e-7)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    manifest = run_plot(
        michel_csv=args.michel_csv,
        params_path=args.params,
        out_dir=args.out_dir,
        seed_with_michel=not bool(args.no_michel_seed),
        dense_points=args.dense_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
    )
    print(
        json.dumps(
            {
                "manifest_path": manifest["manifest_path"],
                "pdf": manifest["plots"]["pdf"],
                "summary_png": manifest["summary_png"],
                "metrics_csv": manifest["metrics_csv"],
                "mapped_metabolites": len(manifest["mapped_metabolites"]),
                "worst": manifest["worst_metabolites"][:5],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
