from pathlib import Path

path = Path(r"C:\Users\Jorgelindo\Desktop\Mario_RBC_up\src\MM_calibration.py")
targets = [
    "vmax_VEGLC",
    "km_EGLC",
    "km_LAC",
    "hybrid_export_hill_VEGLC",
    "hybrid_forward_hill_VLDH",
]

lines = path.read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines, start=1):
    if any(target in line for target in targets):
        start = max(1, i - 3)
        end = min(len(lines), i + 3)
        print(f"--- around line {i} ---")
        for j in range(start, end + 1):
            print(f"{j}: {lines[j-1]}")
