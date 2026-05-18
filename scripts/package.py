"""Build the marketplace-submission ZIP for D&D Campaign Manager.

Usage:
    python scripts/package.py

Produces ``dnd_campaign_manager.zip`` at the repo root, excluding tests,
caches, the local venv, and any previously-built zip.
"""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_ZIP = REPO_ROOT / "dnd_campaign_manager.zip"

INCLUDE_TOP_LEVEL = [
    "__main__.py",
    "manifest.json",
    "requirements.txt",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
]
INCLUDE_DIRS = ["plugin_module"]

EXCLUDE_DIR_NAMES = {
    "__pycache__", ".pytest_cache", ".mypy_cache",
    ".venv", "venv", "env", ".git", ".idea", ".vscode",
    "tests", "scripts", "build", "dist",
}
EXCLUDE_FILE_SUFFIXES = (".pyc", ".pyo")


def _should_include(path: Path) -> bool:
    if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
        return False
    if path.suffix in EXCLUDE_FILE_SUFFIXES:
        return False
    return True


def main() -> int:
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()

    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for top in INCLUDE_TOP_LEVEL:
            p = REPO_ROOT / top
            if not p.exists():
                print(f"[skip] missing: {top}", file=sys.stderr)
                continue
            zf.write(p, arcname=top)

        for dirname in INCLUDE_DIRS:
            root = REPO_ROOT / dirname
            if not root.is_dir():
                print(f"[skip] not a dir: {dirname}", file=sys.stderr)
                continue
            for path in sorted(root.rglob("*")):
                if path.is_dir():
                    continue
                rel = path.relative_to(REPO_ROOT)
                if not _should_include(rel):
                    continue
                zf.write(path, arcname=str(rel).replace(os.sep, "/"))

    size_kb = OUT_ZIP.stat().st_size / 1024
    with zipfile.ZipFile(OUT_ZIP) as zf:
        entries = len(zf.namelist())
    print(f"Built {OUT_ZIP.name}: {size_kb:.1f} KB, {entries} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
