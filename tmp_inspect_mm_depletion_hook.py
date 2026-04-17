from pathlib import Path


def show(path_str: str, patterns: list[str], context: int = 8) -> None:
    path = Path(path_str)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    print(f"\n=== {path} ===")
    for pattern in patterns:
        print(f"\n--- {pattern} ---")
        for idx, line in enumerate(lines, start=1):
            if pattern in line:
                start = max(1, idx - context)
                end = min(len(lines), idx + context)
                for j in range(start, end + 1):
                    print(f"{j}: {lines[j-1]}")
                print("...")


show(
    r"C:\Users\Jorgelindo\Desktop\Mario_RBC_up\src\teacher_flux_autoresearch_glucose.py",
    ["best_executable", "leaderboard", "decision", "candidate_curve_metrics"],
)
show(
    r"C:\Users\Jorgelindo\Desktop\Mario_RBC_up\src\MM_calibration.py",
    [
        "PHASE1_HYBRID_PARAMS",
        "hybrid_blend_VEGLC",
        "hybrid_import_hill_VEGLC",
        "hybrid_reverse_scale_VEGLC",
        "hybrid_glucose_lactate",
    ],
)
