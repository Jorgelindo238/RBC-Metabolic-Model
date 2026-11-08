"""Evaluate a candidate parameter set against the full Brodbar panel.

The script compares the current baseline params against a candidate params JSON
on all Brodbar experimental metabolites that can be mapped to model states.
It writes multi-page plots, long-form predictions, per-metabolite metrics, and
a compact decision summary.
"""

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
DEFAULT_BASELINE_PARAMS = ROOT / "Simulations" / "brodbar" / "calibration" / "best_params.json"
DEFAULT_CANDIDATE_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "transport_gate_eglc_elac_46d_n32_endpoint16"
    / "best_params.json"
)
DEFAULT_OUT_DIR = ROOT / "output" / "brodbar_transport_gate_full_panel"

for path in (str(ROOT), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar  # noqa: E402
from MM_calibration import EXP_TO_MODEL, load_experimental_data, load_initial_conditions  # noqa: E402


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


def _load_params(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for name, value in payload.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out[str(name)] = float(value)
        elif isinstance(value, str):
            out[str(name)] = value
    return out


def _load_brodbar_panel() -> tuple[np.ndarray, dict[str, np.ndarray], list[str], dict[str, int], list[str]]:
    time_exp, exp_values, name_to_row = load_experimental_data()
    order = sorted(name_to_row, key=name_to_row.get)
    curves: dict[str, np.ndarray] = {}
    index_map: dict[str, int] = {}
    unmapped: list[str] = []
    for name in order:
        idx = EXP_TO_MODEL.get(name, BRODBAR_METABOLITE_MAP.get(name))
        if idx is None:
            unmapped.append(name)
            continue
        row = name_to_row[name]
        values = np.asarray(exp_values[row, :], dtype=float)
        if not np.all(np.isfinite(values)):
            continue
        curves[name] = values
        index_map[name] = int(idx)
    return np.asarray(time_exp, dtype=float), curves, [name for name in order if name in curves], index_map, unmapped


def _simulate(
    *,
    x0: np.ndarray,
    params: Mapping[str, Any],
    time_exp: np.ndarray,
    dense_points: int,
    method: str,
    rtol: float,
    atol: float,
) -> Any:
    t_dense = np.linspace(float(time_exp[0]), float(time_exp[-1]), int(dense_points))
    t_eval = np.unique(np.concatenate([t_dense, time_exp]))
    sol = solve_ivp(
        lambda t, y: equadiff_brodbar(
            t,
            y,
            custom_params=dict(params),
            curve_fit_strength=0.0,
        ),
        (float(t_eval[0]), float(t_eval[-1])),
        np.asarray(x0, dtype=float),
        method=method,
        t_eval=t_eval,
        rtol=float(rtol),
        atol=float(atol),
    )
    if not sol.success:
        raise RuntimeError(f"ODE solve failed: {sol.message}")
    sol.y[:] = np.maximum(sol.y, 0.0)
    return sol


def _interp_state(sol: Any, state_idx: int, time_exp: np.ndarray) -> np.ndarray:
    return np.interp(time_exp, np.asarray(sol.t, dtype=float), sol.y[int(state_idx), :])


def _nrmse(sim_values: np.ndarray, exp_values: np.ndarray) -> tuple[float, float, float]:
    rmse = float(np.sqrt(np.mean((sim_values - exp_values) ** 2)))
    norm = float(max(np.mean(np.abs(exp_values)), 0.01))
    endpoint_error = float(abs(sim_values[-1] - exp_values[-1]) / max(abs(float(exp_values[-1])), 0.01))
    return rmse, rmse / norm, endpoint_error


def _compute_metrics(
    *,
    curves: Mapping[str, np.ndarray],
    index_map: Mapping[str, int],
    time_exp: np.ndarray,
    baseline_sol: Any,
    candidate_sol: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metric_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    for name, exp_values in curves.items():
        idx = index_map[name]
        baseline_values = _interp_state(baseline_sol, idx, time_exp)
        candidate_values = _interp_state(candidate_sol, idx, time_exp)
        base_rmse, base_nrmse, base_endpoint = _nrmse(baseline_values, exp_values)
        cand_rmse, cand_nrmse, cand_endpoint = _nrmse(candidate_values, exp_values)
        metric_rows.append(
            {
                "metabolite": name,
                "state_index": int(idx),
                "baseline_rmse": base_rmse,
                "candidate_rmse": cand_rmse,
                "delta_rmse": cand_rmse - base_rmse,
                "baseline_nrmse": base_nrmse,
                "candidate_nrmse": cand_nrmse,
                "delta_nrmse": cand_nrmse - base_nrmse,
                "baseline_endpoint_error": base_endpoint,
                "candidate_endpoint_error": cand_endpoint,
                "delta_endpoint_error": cand_endpoint - base_endpoint,
                "exp_initial": float(exp_values[0]),
                "exp_final": float(exp_values[-1]),
                "baseline_final": float(baseline_values[-1]),
                "candidate_final": float(candidate_values[-1]),
                "baseline_change": float(baseline_values[-1] - baseline_values[0]),
                "candidate_change": float(candidate_values[-1] - candidate_values[0]),
                "exp_change": float(exp_values[-1] - exp_values[0]),
                "status": (
                    "improved"
                    if cand_nrmse < base_nrmse - 0.05
                    else "regressed"
                    if cand_nrmse > base_nrmse + 0.05
                    else "similar"
                ),
            }
        )
        for t, exp_value, baseline_value, candidate_value in zip(
            time_exp,
            exp_values,
            baseline_values,
            candidate_values,
        ):
            prediction_rows.append(
                {
                    "metabolite": name,
                    "time_day": float(t),
                    "experimental": float(exp_value),
                    "baseline": float(baseline_value),
                    "candidate": float(candidate_value),
                }
            )
    metric_rows.sort(key=lambda row: float(row["delta_nrmse"]))
    return metric_rows, prediction_rows


def _plot_full_panel(
    *,
    curves: Mapping[str, np.ndarray],
    index_map: Mapping[str, int],
    order: Sequence[str],
    metrics_rows: Sequence[Mapping[str, Any]],
    time_exp: np.ndarray,
    baseline_sol: Any,
    candidate_sol: Any,
    out_dir: Path,
    per_page: int = 12,
) -> dict[str, Any]:
    metric_by_name = {row["metabolite"]: row for row in metrics_rows}
    pdf_path = out_dir / "brodbar_full_panel_baseline_vs_candidate.pdf"
    png_paths: list[str] = []
    page_count = int(math.ceil(len(order) / per_page))
    with PdfPages(pdf_path) as pdf:
        for page_idx in range(page_count):
            names = list(order[page_idx * per_page : (page_idx + 1) * per_page])
            fig, axes = plt.subplots(4, 3, figsize=(15, 11), constrained_layout=True)
            axes_flat = axes.flatten()
            for ax, name in zip(axes_flat, names):
                idx = index_map[name]
                row = metric_by_name[name]
                ax.plot(
                    baseline_sol.t,
                    baseline_sol.y[idx, :],
                    color="#64748b",
                    linewidth=1.8,
                    label="baseline",
                )
                ax.plot(
                    candidate_sol.t,
                    candidate_sol.y[idx, :],
                    color="#2563eb",
                    linewidth=2.2,
                    label="transport gate",
                )
                ax.scatter(time_exp, curves[name], color="#111827", s=20, zorder=3, label="Brodbar")
                delta = float(row["delta_nrmse"])
                status_color = "#16a34a" if delta < -0.05 else "#dc2626" if delta > 0.05 else "#64748b"
                ax.set_title(
                    f"{name}  {float(row['baseline_nrmse']):.2f}->{float(row['candidate_nrmse']):.2f}",
                    fontsize=10,
                    fontweight="bold",
                    color=status_color,
                )
                ax.set_xlabel("Time (days)", fontsize=8)
                ax.set_ylabel("mM", fontsize=8)
                ax.grid(True, alpha=0.25)
                ax.tick_params(labelsize=8)
            for ax in axes_flat[len(names) :]:
                ax.axis("off")
            handles, labels = axes_flat[0].get_legend_handles_labels()
            fig.legend(handles, labels, loc="upper right", frameon=False, fontsize=9)
            fig.suptitle(
                f"Brodbar full panel: baseline vs transport-gate candidate ({page_idx + 1}/{page_count})",
                fontsize=14,
            )
            pdf.savefig(fig)
            png_path = out_dir / f"brodbar_full_panel_page_{page_idx + 1:02d}.png"
            fig.savefig(png_path, dpi=180)
            png_paths.append(str(png_path))
            plt.close(fig)
    return {"pdf": str(pdf_path), "png_pages": png_paths, "page_count": page_count}


def _plot_delta_summary(metrics_rows: Sequence[Mapping[str, Any]], out_dir: Path, top_n: int = 18) -> str:
    rows = sorted(metrics_rows, key=lambda row: float(row["delta_nrmse"]))
    improvements = rows[:top_n]
    regressions = rows[-top_n:][::-1]
    fig, axes = plt.subplots(1, 2, figsize=(16, 8), constrained_layout=True)
    for ax, selected, title, color in (
        (axes[0], improvements[::-1], "Largest nRMSE improvements", "#16a34a"),
        (axes[1], regressions[::-1], "Largest nRMSE regressions", "#dc2626"),
    ):
        names = [str(row["metabolite"]) for row in selected]
        values = [float(row["delta_nrmse"]) for row in selected]
        ax.barh(names, values, color=color)
        ax.axvline(0.0, color="#111827", linewidth=0.8)
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("candidate nRMSE - baseline nRMSE")
        ax.grid(axis="x", alpha=0.25)
    png_path = out_dir / "brodbar_full_panel_nrmse_delta_summary.png"
    fig.savefig(png_path, dpi=180)
    plt.close(fig)
    return str(png_path)


def _decision(metrics_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_name = {str(row["metabolite"]): row for row in metrics_rows}
    mean_baseline = float(np.mean([float(row["baseline_nrmse"]) for row in metrics_rows]))
    mean_candidate = float(np.mean([float(row["candidate_nrmse"]) for row in metrics_rows]))
    median_baseline = float(np.median([float(row["baseline_nrmse"]) for row in metrics_rows]))
    median_candidate = float(np.median([float(row["candidate_nrmse"]) for row in metrics_rows]))
    improved = [row for row in metrics_rows if row["status"] == "improved"]
    regressed = [row for row in metrics_rows if row["status"] == "regressed"]
    eglc = by_name.get("EGLC", {})
    elac = by_name.get("ELAC", {})
    keep = (
        bool(eglc)
        and float(eglc.get("candidate_endpoint_error", float("inf"))) < 0.10
        and mean_candidate <= mean_baseline * 1.10
    )
    next_action = (
        "keep candidate as VEGLC hypothesis and run a lactate-focused FLA pass on VELAC/VLDH"
        if keep and elac and float(elac.get("candidate_endpoint_error", 0.0)) > 0.20
        else "keep candidate for external validation before global promotion"
        if keep
        else "do not keep candidate; broaden or reweight the transport objective"
    )
    return {
        "mean_nrmse": {"baseline": mean_baseline, "candidate": mean_candidate, "delta": mean_candidate - mean_baseline},
        "median_nrmse": {
            "baseline": median_baseline,
            "candidate": median_candidate,
            "delta": median_candidate - median_baseline,
        },
        "improved_count": len(improved),
        "regressed_count": len(regressed),
        "similar_count": len(metrics_rows) - len(improved) - len(regressed),
        "eglc": eglc,
        "elac": elac,
        "recommendation": next_action,
        "keep_candidate_for_next_stage": bool(keep),
    }


def run_evaluation(
    *,
    baseline_params_path: Path = DEFAULT_BASELINE_PARAMS,
    candidate_params_path: Path = DEFAULT_CANDIDATE_PARAMS,
    out_dir: Path = DEFAULT_OUT_DIR,
    dense_points: int = 240,
    method: str = "LSODA",
    rtol: float = 3e-4,
    atol: float = 1e-6,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    time_exp, curves, order, index_map, unmapped = _load_brodbar_panel()
    x0 = np.asarray(load_initial_conditions(), dtype=float)
    baseline_params = _load_params(Path(baseline_params_path))
    candidate_params = _load_params(Path(candidate_params_path))

    baseline_sol = _simulate(
        x0=x0,
        params=baseline_params,
        time_exp=time_exp,
        dense_points=dense_points,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    candidate_sol = _simulate(
        x0=x0,
        params=candidate_params,
        time_exp=time_exp,
        dense_points=dense_points,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    metrics_rows, prediction_rows = _compute_metrics(
        curves=curves,
        index_map=index_map,
        time_exp=time_exp,
        baseline_sol=baseline_sol,
        candidate_sol=candidate_sol,
    )

    metrics_csv = out_dir / "brodbar_full_panel_metrics.csv"
    predictions_csv = out_dir / "brodbar_full_panel_predictions.csv"
    pd.DataFrame(metrics_rows).sort_values("delta_nrmse").to_csv(metrics_csv, index=False)
    pd.DataFrame(prediction_rows).to_csv(predictions_csv, index=False)

    pages = _plot_full_panel(
        curves=curves,
        index_map=index_map,
        order=order,
        metrics_rows=metrics_rows,
        time_exp=time_exp,
        baseline_sol=baseline_sol,
        candidate_sol=candidate_sol,
        out_dir=out_dir,
    )
    delta_summary_png = _plot_delta_summary(metrics_rows, out_dir)
    decision = _decision(metrics_rows)

    manifest = {
        "contract_type": "brodbar_full_panel_candidate_evaluation",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_params_path": str(baseline_params_path),
        "candidate_params_path": str(candidate_params_path),
        "out_dir": str(out_dir),
        "solver": {
            "method": method,
            "rtol": float(rtol),
            "atol": float(atol),
            "dense_points": int(dense_points),
            "t_start": float(time_exp[0]),
            "t_end": float(time_exp[-1]),
        },
        "mapped_metabolites": list(order),
        "unmapped_metabolites": list(unmapped),
        "metrics_csv": str(metrics_csv),
        "predictions_csv": str(predictions_csv),
        "plots": pages,
        "delta_summary_png": delta_summary_png,
        "decision": decision,
        "top_improvements": sorted(metrics_rows, key=lambda row: float(row["delta_nrmse"]))[:12],
        "top_regressions": sorted(metrics_rows, key=lambda row: float(row["delta_nrmse"]), reverse=True)[:12],
    }
    manifest_path = out_dir / "manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(_jsonable(manifest), indent=2), encoding="utf-8")
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Brodbar full panel baseline vs candidate params")
    parser.add_argument("--baseline-params", type=Path, default=DEFAULT_BASELINE_PARAMS)
    parser.add_argument("--candidate-params", type=Path, default=DEFAULT_CANDIDATE_PARAMS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--dense-points", type=int, default=240)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    manifest = run_evaluation(
        baseline_params_path=args.baseline_params,
        candidate_params_path=args.candidate_params,
        out_dir=args.out_dir,
        dense_points=args.dense_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
    )
    decision = manifest["decision"]
    print(
        json.dumps(
            {
                "manifest_path": manifest["manifest_path"],
                "metrics_csv": manifest["metrics_csv"],
                "predictions_csv": manifest["predictions_csv"],
                "pdf": manifest["plots"]["pdf"],
                "delta_summary_png": manifest["delta_summary_png"],
                "mapped_metabolites": len(manifest["mapped_metabolites"]),
                "unmapped_metabolites": manifest["unmapped_metabolites"],
                "mean_nrmse": decision["mean_nrmse"],
                "median_nrmse": decision["median_nrmse"],
                "counts": {
                    "improved": decision["improved_count"],
                    "regressed": decision["regressed_count"],
                    "similar": decision["similar_count"],
                },
                "eglc": {
                    "baseline_nrmse": decision["eglc"].get("baseline_nrmse"),
                    "candidate_nrmse": decision["eglc"].get("candidate_nrmse"),
                    "baseline_final": decision["eglc"].get("baseline_final"),
                    "candidate_final": decision["eglc"].get("candidate_final"),
                    "exp_final": decision["eglc"].get("exp_final"),
                },
                "elac": {
                    "baseline_nrmse": decision["elac"].get("baseline_nrmse"),
                    "candidate_nrmse": decision["elac"].get("candidate_nrmse"),
                    "baseline_final": decision["elac"].get("baseline_final"),
                    "candidate_final": decision["elac"].get("candidate_final"),
                    "exp_final": decision["elac"].get("exp_final"),
                },
                "recommendation": decision["recommendation"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
