from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT_DIR / "VERSION"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


@lru_cache(maxsize=1)
def read_version() -> str:
    try:
        raw = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"

    cleaned = raw[1:] if raw.startswith("v") else raw
    if SEMVER_RE.fullmatch(cleaned):
        return cleaned
    return "0.0.0"
