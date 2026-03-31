#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ROOT_DIR="${ROOT_DIR}" python3 - <<'PY'
from pathlib import Path
import os
import sys

root = Path(os.environ["ROOT_DIR"])
blocked = []

protected_dirs = [
    root / "backend/media/verification_docs",
    root / "backend/media/exports",
]

for directory in protected_dirs:
    if not directory.exists():
        continue
    for path in directory.rglob("*"):
        if path.is_file() and path.name != ".gitkeep":
            blocked.append(path.relative_to(root).as_posix())

if blocked:
    print("Sensitive runtime artifacts detected:", file=sys.stderr)
    for item in blocked:
        print(f"- {item}", file=sys.stderr)
    sys.exit(1)

print("No sensitive runtime artifacts detected")
PY
