from __future__ import annotations

import fcntl
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .prereq import APP_SUPPORT_DIR, log_event

LAUNCH_STATE_PATH = APP_SUPPORT_DIR / "launch_state.json"
UI_LOCK_PATH = APP_SUPPORT_DIR / "ui.lock"

FAILURE_WINDOW_SECONDS = 60
FAILURE_THRESHOLD = 3
BLOCK_SECONDS = 300


@dataclass
class UiInstanceLock:
    file_handle: Any
    path: Path


def _ensure_support_dir() -> None:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)


def _now_seconds() -> float:
    return time.time()


def _load_launch_state() -> dict[str, Any]:
    _ensure_support_dir()
    if not LAUNCH_STATE_PATH.exists():
        return {"failure_timestamps": [], "blocked_until": None}
    try:
        payload = json.loads(LAUNCH_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"failure_timestamps": [], "blocked_until": None}

    failures = payload.get("failure_timestamps", [])
    if not isinstance(failures, list):
        failures = []

    blocked_until = payload.get("blocked_until")
    if blocked_until is not None and not isinstance(blocked_until, (int, float)):
        blocked_until = None

    return {"failure_timestamps": failures, "blocked_until": blocked_until}


def _save_launch_state(state: dict[str, Any]) -> None:
    _ensure_support_dir()
    LAUNCH_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _prune_failures(failures: list[float], now: float) -> list[float]:
    cutoff = now - FAILURE_WINDOW_SECONDS
    return [float(ts) for ts in failures if isinstance(ts, (int, float)) and float(ts) >= cutoff]


def check_temporary_block(now: float | None = None) -> tuple[bool, int]:
    current = _now_seconds() if now is None else now
    state = _load_launch_state()
    failures = _prune_failures(state.get("failure_timestamps", []), current)
    blocked_until = state.get("blocked_until")

    if isinstance(blocked_until, (int, float)) and blocked_until > current:
        remaining = max(1, int(math.ceil(blocked_until - current)))
        if failures != state.get("failure_timestamps"):
            state["failure_timestamps"] = failures
            _save_launch_state(state)
        return True, remaining

    if blocked_until is not None or failures != state.get("failure_timestamps"):
        state["blocked_until"] = None
        state["failure_timestamps"] = failures
        _save_launch_state(state)

    return False, 0


def record_launch_failure(now: float | None = None) -> tuple[bool, int]:
    current = _now_seconds() if now is None else now
    state = _load_launch_state()
    failures = _prune_failures(state.get("failure_timestamps", []), current)
    failures.append(current)
    state["failure_timestamps"] = failures

    if len(failures) >= FAILURE_THRESHOLD:
        blocked_until = current + BLOCK_SECONDS
        state["blocked_until"] = blocked_until
        _save_launch_state(state)
        remaining = max(1, int(math.ceil(BLOCK_SECONDS)))
        log_event(
            "launch_safety_blocked "
            f"failures_in_window={len(failures)} blocked_until={blocked_until:.3f}"
        )
        return True, remaining

    state["blocked_until"] = None
    _save_launch_state(state)
    log_event(f"launch_failure_recorded failures_in_window={len(failures)}")
    return False, 0


def record_launch_success() -> None:
    state = {"failure_timestamps": [], "blocked_until": None}
    _save_launch_state(state)
    log_event("launch_success_reset_failures")


def acquire_ui_lock() -> UiInstanceLock | None:
    _ensure_support_dir()
    handle = UI_LOCK_PATH.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None

    handle.seek(0)
    handle.write(str(os.getpid()))
    handle.truncate()
    handle.flush()
    return UiInstanceLock(file_handle=handle, path=UI_LOCK_PATH)


def release_ui_lock(lock: UiInstanceLock | None) -> None:
    if lock is None:
        return
    try:
        fcntl.flock(lock.file_handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        lock.file_handle.close()
    except OSError:
        pass
