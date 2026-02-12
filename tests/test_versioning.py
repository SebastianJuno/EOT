from __future__ import annotations

import json
from pathlib import Path

from backend.app import app
from backend.versioning import read_version
from desktop import prereq


def test_version_file_is_backend_source_of_truth() -> None:
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    expected = version_file.read_text(encoding="utf-8").strip()
    read_version.cache_clear()
    assert read_version() == expected


def test_fastapi_app_version_matches_version_file() -> None:
    assert app.version == read_version()


def test_desktop_config_last_version_seen_matches_version_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(prereq, "APP_SUPPORT_DIR", tmp_path)
    monkeypatch.setattr(prereq, "CONFIG_PATH", tmp_path / "config.json")
    prereq._write_config(java_ok=True)
    payload = json.loads(prereq.CONFIG_PATH.read_text(encoding="utf-8"))
    assert payload["last_version_seen"] == read_version()
