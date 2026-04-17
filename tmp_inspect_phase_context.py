from pathlib import Path
import sys


path = Path(sys.argv[1])
patterns = sys.argv[2:]
lines = path.read_text(encoding="utf-8").splitlines()
for index, line in enumerate(lines, start=1):
    if any(pattern in line for pattern in patterns):
        print(f"{index}:{line}")
