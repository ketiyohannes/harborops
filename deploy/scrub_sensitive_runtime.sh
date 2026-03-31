#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ROOT_DIR_ENV="${ROOT_DIR}"

ROOT_DIR="${ROOT_DIR_ENV}" python3 - <<'PY'
from pathlib import Path
import os

root = Path(os.environ["ROOT_DIR"])

targets = [
    root / "backend/media/verification_docs",
    root / "backend/media/exports",
]

deleted = 0
for target in targets:
    if not target.exists():
        continue
    for path in sorted(target.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink(missing_ok=True)
            deleted += 1
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass

print(f"Removed {deleted} sensitive runtime files")
PY

echo "Sensitive runtime artifact scrub complete"
