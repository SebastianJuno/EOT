from __future__ import annotations

from pathlib import Path

import desktop.backend_runner as backend_runner


class DummyProcess:
    def __init__(self, returncode: int | None = None, pid: int = 4321):
        self.returncode = returncode
        self.pid = pid

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


class DummyThread:
    def __init__(self, alive: bool = False):
        self._alive = alive

    def is_alive(self) -> bool:
        return self._alive


def test_backend_spawn_uses_backend_mode_flag(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    def fake_popen(cmd, stdout=None, stderr=None, env=None):
        calls["cmd"] = cmd
        calls["stdout"] = stdout
        calls["stderr"] = stderr
        calls["env"] = env
        return DummyProcess(returncode=None, pid=9999)

    monkeypatch.setattr(backend_runner, "_find_free_port", lambda: 19001)
    monkeypatch.setattr(
        backend_runner,
        "_open_backend_log_file",
        lambda: (tmp_path / "backend.log").open("ab"),
    )
    monkeypatch.setattr(backend_runner, "_runtime_env", lambda: {"PATH": "/usr/bin"})
    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(backend_runner.sys, "executable", "/Applications/EOT Diff Tool")
    monkeypatch.setattr(backend_runner.sys, "frozen", False, raising=False)
    monkeypatch.setattr(backend_runner, "BACKEND_LOG_PATH", tmp_path / "backend.log")
    monkeypatch.setattr(backend_runner, "log_event", lambda *_: None)

    handle = backend_runner.start_backend()

    cmd = calls["cmd"]
    assert isinstance(cmd, list)
    assert "--backend-mode" in cmd
    assert "-m" in cmd
    assert "desktop.main" in cmd
    assert handle.port == 19001
    assert handle.pid == 9999


def test_backend_frozen_mode_uses_inprocess_backend(monkeypatch, tmp_path: Path):
    calls: dict[str, int] = {"popen": 0}
    fake_handle = backend_runner.BackendHandle(
        process=None,
        base_url="http://127.0.0.1:19004",
        port=19004,
        session_id="session-inproc",
        pid=123,
        backend_log_path=tmp_path / "backend.log",
        launch_cmd=["<inprocess>"],
    )

    def fake_popen(*_args, **_kwargs):
        calls["popen"] += 1
        return DummyProcess(returncode=None, pid=9999)

    monkeypatch.setattr(backend_runner, "_start_backend_inprocess", lambda **_kwargs: fake_handle)
    monkeypatch.setattr(backend_runner, "_find_free_port", lambda: 19004)
    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(backend_runner.sys, "frozen", True, raising=False)

    handle = backend_runner.start_backend()
    assert handle is fake_handle
    assert handle.process is None
    assert calls["popen"] == 0


def test_health_check_fails_fast_on_child_exit(tmp_path: Path):
    log_path = tmp_path / "backend.log"
    log_path.write_text("ERROR Address already in use", encoding="utf-8")

    handle = backend_runner.BackendHandle(
        process=DummyProcess(returncode=1, pid=321),
        base_url="http://127.0.0.1:19002",
        port=19002,
        session_id="session-a",
        pid=321,
        backend_log_path=log_path,
        launch_cmd=[],
    )

    result = backend_runner.wait_for_health(handle, timeout_seconds=1.0)

    assert result.ok is False
    assert result.reason == "port_bind_issue"
    assert result.exit_code == 1


def test_backend_log_path_recorded_in_failure_reason(tmp_path: Path):
    log_path = tmp_path / "backend.log"
    log_path.write_text("ModuleNotFoundError: No module named 'uvicorn'\n", encoding="utf-8")

    handle = backend_runner.BackendHandle(
        process=DummyProcess(returncode=1, pid=322),
        base_url="http://127.0.0.1:19003",
        port=19003,
        session_id="session-b",
        pid=322,
        backend_log_path=log_path,
        launch_cmd=[],
    )

    result = backend_runner.wait_for_health(handle, timeout_seconds=1.0)

    assert result.ok is False
    assert result.reason == "missing_dependency"
    assert "ModuleNotFoundError" in result.details


def test_health_check_fails_fast_if_inprocess_thread_ended_without_exit_code(tmp_path: Path):
    handle = backend_runner.BackendHandle(
        process=None,
        base_url="http://127.0.0.1:19005",
        port=19005,
        session_id="session-c",
        pid=323,
        backend_log_path=tmp_path / "backend.log",
        launch_cmd=["<inprocess>"],
        inprocess=backend_runner.InProcessBackend(thread=DummyThread(alive=False)),
    )

    result = backend_runner.wait_for_health(handle, timeout_seconds=1.0)

    assert result.ok is False
    assert result.reason == "exited_early"
    assert result.exit_code == 1
