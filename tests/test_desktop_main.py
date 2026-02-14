from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import desktop.main as launcher_main


def _fake_handle(port: int, pid: int):
    return launcher_main.BackendHandle(
        process=None,  # type: ignore[arg-type]
        base_url=f"http://127.0.0.1:{port}",
        port=port,
        session_id=f"session-{port}",
        pid=pid,
        backend_log_path=Path("/tmp/backend.log"),
        launch_cmd=[],
    )


class _FakeSplash:
    def __init__(self):
        self.updates: list[tuple[int, int, str]] = []
        self.loaded_urls: list[str] = []
        self.closed = 0

    def update(self, step: int, total: int, message: str) -> None:
        self.updates.append((step, total, message))

    def load_app(self, base_url: str) -> None:
        self.loaded_urls.append(base_url)

    def close(self) -> None:
        self.closed += 1


def test_backend_mode_does_not_run_ui_prereq_path(monkeypatch):
    called = {}

    def fake_backend_mode(host: str, port: int, session_id: str) -> int:
        called["host"] = host
        called["port"] = port
        called["session_id"] = session_id
        return 0

    def should_not_be_called():
        raise AssertionError("UI prerequisite path should not run in backend mode")

    monkeypatch.setattr(launcher_main, "_run_backend_mode", fake_backend_mode)
    monkeypatch.setattr(launcher_main, "check_prerequisites", should_not_be_called)

    rc = launcher_main.main(
        ["--backend-mode", "--host", "127.0.0.1", "--port", "19100", "--session-id", "abc"]
    )

    assert rc == 0
    assert called == {"host": "127.0.0.1", "port": 19100, "session_id": "abc"}


def test_one_retry_then_fail(monkeypatch):
    calls = {"start": 0, "shown": 0}
    handles = [_fake_handle(19101, 5001), _fake_handle(19102, 5002)]
    splash = _FakeSplash()

    def fake_start_backend():
        idx = calls["start"]
        calls["start"] += 1
        return handles[idx]

    def fake_wait_for_health(_handle, timeout_seconds=30):
        return launcher_main.HealthCheckResult(
            ok=False,
            reason="timeout",
            exit_code=None,
            details="timed out",
            elapsed_seconds=timeout_seconds,
        )

    def fake_show_backend_failure(*_args, **_kwargs):
        calls["shown"] += 1

    monkeypatch.setattr(launcher_main, "acquire_ui_lock", lambda: object())
    monkeypatch.setattr(launcher_main, "release_ui_lock", lambda _lock: None)
    monkeypatch.setattr(launcher_main, "check_temporary_block", lambda: (False, 0))
    monkeypatch.setattr(launcher_main, "check_prerequisites", lambda: SimpleNamespace(ok=True, message=""))
    monkeypatch.setattr(launcher_main, "start_backend", fake_start_backend)
    monkeypatch.setattr(launcher_main, "wait_for_health", fake_wait_for_health)
    monkeypatch.setattr(launcher_main, "stop_backend", lambda _handle: None)
    monkeypatch.setattr(launcher_main, "record_launch_failure", lambda: (False, 0))
    monkeypatch.setattr(launcher_main, "_show_backend_failure", fake_show_backend_failure)
    monkeypatch.setattr(launcher_main, "log_event", lambda *_: None)
    monkeypatch.setattr(launcher_main.time, "sleep", lambda _sec: None)
    monkeypatch.setattr(launcher_main, "launch_with_startup_splash", lambda run: run(splash))

    rc = launcher_main._run_ui_mode()

    assert rc == 1
    assert calls["start"] == 2
    assert calls["shown"] == 1
    assert splash.closed >= 1


def test_failure_dialog_payload_includes_log_path(monkeypatch):
    captured = {}

    def fake_show_error(title: str, message: str, allow_open_logs: bool = False):
        captured["title"] = title
        captured["message"] = message
        captured["allow_open_logs"] = allow_open_logs

    monkeypatch.setattr(launcher_main, "_show_error", fake_show_error)

    launcher_main._show_backend_failure(
        handle=_fake_handle(19103, 5003),
        result=launcher_main.HealthCheckResult(
            ok=False,
            reason="timeout",
            exit_code=None,
            details="timeout",
            elapsed_seconds=30.0,
        ),
        blocked_now=False,
        blocked_seconds=0,
    )

    assert captured["title"] == "Backend Error"
    assert str(launcher_main.LOG_DIR) in captured["message"]
    assert captured["allow_open_logs"] is True


def test_startup_stage_emission_order_on_success(monkeypatch):
    stage_log: list[str] = []
    opened: list[str] = []

    monkeypatch.setattr(launcher_main, "check_temporary_block", lambda: (False, 0))
    monkeypatch.setattr(launcher_main, "check_prerequisites", lambda: SimpleNamespace(ok=True, message=""))
    monkeypatch.setattr(launcher_main, "start_backend", lambda: _fake_handle(19110, 6010))
    monkeypatch.setattr(
        launcher_main,
        "wait_for_health",
        lambda _handle, timeout_seconds=30: launcher_main.HealthCheckResult(
            ok=True,
            reason="healthy",
            exit_code=None,
            details="",
            elapsed_seconds=0.2,
        ),
    )
    monkeypatch.setattr(launcher_main, "record_launch_success", lambda: None)
    monkeypatch.setattr(launcher_main, "log_event", lambda *_: None)

    rc, _handle = launcher_main._run_startup_sequence(
        show_progress=lambda step, total, message: stage_log.append(f"{step}/{total}:{message}"),
        close_progress=lambda: None,
        open_app=lambda base_url: opened.append(base_url),
    )

    assert rc == 0
    assert opened == ["http://127.0.0.1:19110"]
    assert stage_log == [
        "1/5:Checking startup safety",
        "2/5:Checking prerequisites",
        "3/5:Starting backend (attempt 1/2)",
        "4/5:Waiting for backend health (attempt 1/2)",
        "5/5:Opening application window",
    ]


def test_splash_success_transitions_to_app_url(monkeypatch):
    splash = _FakeSplash()
    released = {"count": 0}
    stopped: list[int] = []

    monkeypatch.setattr(launcher_main, "acquire_ui_lock", lambda: object())
    monkeypatch.setattr(launcher_main, "release_ui_lock", lambda _lock: released.__setitem__("count", released["count"] + 1))
    monkeypatch.setattr(launcher_main, "check_temporary_block", lambda: (False, 0))
    monkeypatch.setattr(launcher_main, "check_prerequisites", lambda: SimpleNamespace(ok=True, message=""))
    monkeypatch.setattr(launcher_main, "start_backend", lambda: _fake_handle(19111, 6011))
    monkeypatch.setattr(
        launcher_main,
        "wait_for_health",
        lambda _handle, timeout_seconds=30: launcher_main.HealthCheckResult(
            ok=True,
            reason="healthy",
            exit_code=None,
            details="",
            elapsed_seconds=0.1,
        ),
    )
    monkeypatch.setattr(launcher_main, "record_launch_success", lambda: None)
    monkeypatch.setattr(launcher_main, "stop_backend", lambda handle: stopped.append(handle.port) if handle else None)
    monkeypatch.setattr(launcher_main, "log_event", lambda *_: None)
    monkeypatch.setattr(launcher_main, "launch_with_startup_splash", lambda run: run(splash))

    rc = launcher_main._run_ui_mode()

    assert rc == 0
    assert splash.loaded_urls == ["http://127.0.0.1:19111"]
    assert released["count"] == 1
    assert stopped == [19111]


def test_splash_failure_surfaces_backend_error(monkeypatch):
    splash = _FakeSplash()
    shown = {"count": 0}

    monkeypatch.setattr(launcher_main, "acquire_ui_lock", lambda: object())
    monkeypatch.setattr(launcher_main, "release_ui_lock", lambda _lock: None)
    monkeypatch.setattr(launcher_main, "check_temporary_block", lambda: (False, 0))
    monkeypatch.setattr(launcher_main, "check_prerequisites", lambda: SimpleNamespace(ok=True, message=""))
    monkeypatch.setattr(launcher_main, "start_backend", lambda: _fake_handle(19112, 6012))
    monkeypatch.setattr(
        launcher_main,
        "wait_for_health",
        lambda _handle, timeout_seconds=30: launcher_main.HealthCheckResult(
            ok=False,
            reason="timeout",
            exit_code=None,
            details="timeout",
            elapsed_seconds=timeout_seconds,
        ),
    )
    monkeypatch.setattr(launcher_main, "stop_backend", lambda _handle: None)
    monkeypatch.setattr(launcher_main, "record_launch_failure", lambda: (False, 0))
    monkeypatch.setattr(launcher_main, "_show_backend_failure", lambda *_args, **_kwargs: shown.__setitem__("count", shown["count"] + 1))
    monkeypatch.setattr(launcher_main, "log_event", lambda *_: None)
    monkeypatch.setattr(launcher_main.time, "sleep", lambda _sec: None)
    monkeypatch.setattr(launcher_main, "launch_with_startup_splash", lambda run: run(splash))

    rc = launcher_main._run_ui_mode()

    assert rc == 1
    assert shown["count"] == 1
    assert splash.closed >= 1
