from pathlib import Path

path = Path(r"C:\Users\Jorgelindo\Desktop\Mario_RBC_up\src\MM_calibration.py")
lines = path.read_text(encoding="utf-8").splitlines()

ranges = [
    (1418, 1535),
    (1568, 1615),
    (1790, 1915),
    (1988, 2028),
    (3000, 3075),
    (3580, 3675),
]

for start, end in ranges:
    print(f"=== {start}-{end} ===")
    for i in range(start, end + 1):
        print(f"{i}: {lines[i-1]}")
