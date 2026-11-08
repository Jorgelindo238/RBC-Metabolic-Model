"""Minimal smoke test for dump_trajectories plumbing.

Calls run_calibration directly with n_trials=1, dump_trajectories=True, and
verifies that metabolites/all_metabolites.csv is produced.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from MM_calibration import run_calibration

OUT_DIR = ROOT / "tmp_ode_diag" / "dump_traj_smoke"
OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"[smoke] out_dir: {OUT_DIR}")
print("[smoke] calling run_calibration(n_trials=1, dump_trajectories=True)...")

current_params, final_loss, trajectory_csv_path = run_calibration(
    phases=[1],
    n_trials=1,
    global_trials=0,
    target_scope="glycolysis_extracellular",
    param_scope="glycolysis_extracellular",
    generate_plots=False,
    seed=42,
    t_max=46,
    out_dir=str(OUT_DIR),
    optimization_strategy="legacy",
    dump_trajectories=True,
)

print(f"\n[smoke] final_loss: {final_loss}")
print(f"[smoke] trajectory_csv_path: {trajectory_csv_path}")

if trajectory_csv_path is None:
    print("[FAIL] trajectory_csv_path is None")
    sys.exit(1)

csv_path = Path(trajectory_csv_path)
if not csv_path.exists():
    print(f"[FAIL] CSV does not exist at {csv_path}")
    sys.exit(1)

# Inspect the CSV
import pandas as pd
df = pd.read_csv(csv_path)
print(f"\n[smoke] CSV shape: {df.shape}")
print(f"[smoke] First 5 columns: {list(df.columns[:5])}")
print(f"[smoke] Last 3 columns: {list(df.columns[-3:])}")
print(f"[smoke] Time range: {df['Time (days)'].min():.3f} to {df['Time (days)'].max():.3f}")
print(f"[smoke] Has ATP column: {'ATP' in df.columns}")
print(f"[smoke] Has B23PG column: {'B23PG' in df.columns}")
print(f"[smoke] Has GSH column: {'GSH' in df.columns}")

print("\n[PASS] dump_trajectories plumbing works end-to-end.")
