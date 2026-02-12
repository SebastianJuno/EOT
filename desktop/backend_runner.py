from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import resource_path
from .prereq import BACKEND_LOG_PATH, log_event


@dataclass
class BackendHandle:
    process: subprocess.Popen
    base_url: str
    port: int
    session_id: str
    pid: int
    backend_log_path: Path
    launch_cmd: list[str]


@dataclass
class HealthCheckResult:
    ok: bool
    reason: str
    exit_code: int | None
    details: str
    elapsed_seconds: float


def _find_free_port(start: int = 18000, end: int = 20000) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No free local port found for backend")


def _open_backend_log_file() -> Any:
    BACKEND_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    return BACKEND_LOG_PATH.open("ab")


def _tail_backend_log(path: Path, max_bytes: int = 8192) -> str:
    if not path.exists():
        return ""
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data[-max_bytes:].decode("utf-8", errors="replace")


def _classify_exit_reason(log_tail: str) -> str:
    lowered = log_tail.lower()
    if "address already in use" in lowered:
        return "port_bind_issue"
    if "modulenotfounderror" in lowered or "no module named" in lowered:
        return "missing_dependency"
    return "exited_early"


def wait_for_health(handle: BackendHandle, timeout_seconds: float = 30.0) -> HealthCheckResult:
    health = f"{handle.base_url}/health"
    start = time.monotonic()
    deadline = start + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        exit_code = handle.process.poll()
        if exit_code is not None:
            log_tail = _tail_backend_log(handle.backend_log_path)
            reason = _classify_exit_reason(log_tail)
            return HealthCheckResult(
                ok=False,
                reason=reason,
                exit_code=exit_code,
                details=log_tail[-1200:],
                elapsed_seconds=time.monotonic() - start,
            )

        try:
            with urllib.request.urlopen(health, timeout=1.5) as response:
                if response.status == 200:
                    return HealthCheckResult(
                        ok=True,
                        reason="healthy",
                        exit_code=None,
                        details="",
                        elapsed_seconds=time.monotonic() - start,
                    )
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
            time.sleep(0.3)

    exit_code = handle.process.poll()
    if exit_code is not None:
        log_tail = _tail_backend_log(handle.backend_log_path)
        reason = _classify_exit_reason(log_tail)
        return HealthCheckResult(
            ok=False,
            reason=reason,
            exit_code=exit_code,
            details=log_tail[-1200:],
            elapsed_seconds=time.monotonic() - start,
        )

    return HealthCheckResult(
        ok=False,
        reason="timeout",
        exit_code=None,
        details=last_error,
        elapsed_seconds=time.monotonic() - start,
    )


def _runtime_env() -> dict[str, str]:
    env = os.environ.copy()

    parser_jar = resource_path("java-parser", "target", "mpp-extractor-1.0.0-jar-with-dependencies.jar")
    frontend_dir = resource_path("frontend")

    env["EOT_PARSER_JAR"] = str(parser_jar)
    env["EOT_FRONTEND_DIR"] = str(frontend_dir)

    # Prefer Homebrew OpenJDK locations if available.
    extra_java_paths = [
        "/opt/homebrew/opt/openjdk@17/bin",
        "/usr/local/opt/openjdk@17/bin",
    ]
    path = env.get("PATH", "")
    for java_path in extra_java_paths:
        if Path(java_path).exists() and java_path not in path:
            path = f"{java_path}:{path}" if path else java_path
    env["PATH"] = path

    return env


def _backend_command(port: int, session_id: str) -> list[str]:
    base_args = [
        "--backend-mode",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--session-id",
        session_id,
    ]
    if getattr(sys, "frozen", False):
        return [sys.executable, *base_args]
    return [sys.executable, "-m", "desktop.main", *base_args]


def start_backend() -> BackendHandle:
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    session_id = f"{int(time.time() * 1000)}-{port}"
    cmd = _backend_command(port=port, session_id=session_id)
    log_file = _open_backend_log_file()
    process = subprocess.Popen(cmd, stdout=log_file, stderr=log_file, env=_runtime_env())
    log_file.close()

    handle = BackendHandle(
        process=process,
        base_url=base_url,
        port=port,
        session_id=session_id,
        pid=process.pid,
        backend_log_path=BACKEND_LOG_PATH,
        launch_cmd=cmd,
    )
    log_event(
        f"backend_start session_id={handle.session_id} pid={handle.pid} "
        f"port={handle.port} cmd={' '.join(handle.launch_cmd)}"
    )
    return handle


def stop_backend(handle: BackendHandle | None) -> None:
    if handle is None:
        return
    if handle.process.poll() is not None:
        log_event(
            f"backend_stop_skipped_already_exited session_id={handle.session_id} "
            f"pid={handle.pid} exit_code={handle.process.returncode}"
        )
        return
    log_event(f"backend_stop_terminate session_id={handle.session_id} pid={handle.pid}")
    handle.process.terminate()
    try:
        handle.process.wait(timeout=5)
        log_event(
            f"backend_stopped session_id={handle.session_id} pid={handle.pid} "
            f"exit_code={handle.process.returncode}"
        )
    except subprocess.TimeoutExpired:
        log_event(f"backend_stop_kill session_id={handle.session_id} pid={handle.pid}")
        handle.process.kill()
        handle.process.wait(timeout=3)
        log_event(
            f"backend_killed session_id={handle.session_id} pid={handle.pid} "
            f"exit_code={handle.process.returncode}"
        )
