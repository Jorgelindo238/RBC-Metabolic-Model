import json
from pathlib import Path

seed_path = Path(r"C:\Users\Jorgelindo\Desktop\Mario_RBC_up\Simulations\brodbar\calibration\hybrid_teacher_flux_local_veglc_velac_vldh_seed_promoted\best_params.json")
run_path = Path(r"C:\Users\Jorgelindo\Desktop\Mario_RBC_up\Simulations\brodbar\calibration\promoted_local_triplet_seed_veglc_velac_vldh_coupled_longrun_rerun_bounds_aligned\best_params.json")

seed = json.loads(seed_path.read_text())
run = json.loads(run_path.read_text())

diffs = []
for key in sorted(set(seed) | set(run)):
    if seed.get(key) != run.get(key):
        diffs.append((key, seed.get(key), run.get(key)))

print(f"DIFF_COUNT {len(diffs)}")
for key, a, b in diffs:
    print(f"{key}: {a} -> {b}")
