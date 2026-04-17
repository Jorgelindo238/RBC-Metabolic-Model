from pathlib import Path
import sys

path = Path(sys.argv[1])
start = int(sys.argv[2])
end = int(sys.argv[3])
lines = path.read_text(encoding="utf-8").splitlines()
for i in range(start - 1, min(end, len(lines))):
    print(f"{i+1}: {lines[i]}")
