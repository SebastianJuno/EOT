from __future__ import annotations

from pathlib import Path

import desktop.safety as safety


def _patch_paths(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(safety, "APP_SUPPORT_DIR", tmp_path)
    monkeypatch.setattr(safety, "LAUNCH_STATE_PATH", tmp_path / "launch_state.json")
    monkeypatch.setattr(safety, "UI_LOCK_PATH", tmp_path / "ui.lock")
    monkeypatch.setattr(safety, "log_event", lambda *_: None)


def test_ui_single_instance_blocks_second_start(monkeypatch, tmp_path: Path):
    _patch_paths(monkeypatch, tmp_path)

    first = safety.acquire_ui_lock()
    second = safety.acquire_ui_lock()

    assert first is not None
    assert second is None

    safety.release_ui_lock(first)
    third = safety.acquire_ui_lock()
    assert third is not None
    safety.release_ui_lock(third)


def test_safety_breaker_blocks_after_repeated_failures(monkeypatch, tmp_path: Path):
    _patch_paths(monkeypatch, tmp_path)

    blocked1, _ = safety.record_launch_failure(now=100.0)
    blocked2, _ = safety.record_launch_failure(now=130.0)
    blocked3, remaining = safety.record_launch_failure(now=150.0)

    assert blocked1 is False
    assert blocked2 is False
    assert blocked3 is True
    assert remaining >= 300

    is_blocked, remaining_now = safety.check_temporary_block(now=151.0)
    assert is_blocked is True
    assert remaining_now > 0

    blocked_after_expiry, _ = safety.check_temporary_block(now=451.0)
    assert blocked_after_expiry is False
