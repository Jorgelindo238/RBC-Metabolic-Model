from pathlib import Path

path = Path(r"src\MM_calibration.py")
lines = path.read_text(encoding="utf-8").splitlines()

for start, end in [(535, 600), (720, 770), (790, 940)]:
    print(f"RANGE {start}-{end}")
    for idx in range(start, end + 1):
        safe = lines[idx - 1].encode("cp1252", errors="replace").decode("cp1252")
        print(f"{idx}: {safe}")
