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

from .paths import resource_path


@dataclass
class BackendHandle:
    process: subprocess.Popen
    base_url: str


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


def wait_for_health(base_url: str, timeout_seconds: float = 30.0) -> bool:
    health = f"{base_url}/health"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=1.5) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.3)
    return False


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


def start_backend() -> BackendHandle:
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_runtime_env(),
    )

    return BackendHandle(process=process, base_url=base_url)


def stop_backend(handle: BackendHandle | None) -> None:
    if handle is None:
        return
    if handle.process.poll() is not None:
        return
    handle.process.terminate()
    try:
        handle.process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        handle.process.kill()
        handle.process.wait(timeout=3)
