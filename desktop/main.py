from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from desktop.backend_runner import (
    BackendHandle,
    HealthCheckResult,
    start_backend,
    stop_backend,
    wait_for_health,
)
from desktop.prereq import LOG_DIR, check_prerequisites, install_prerequisites, log_event
from desktop.safety import (
    acquire_ui_lock,
    check_temporary_block,
    record_launch_failure,
    record_launch_success,
    release_ui_lock,
)
from desktop.window import launch_window, launch_with_startup_splash

JAVA17_URL = "https://adoptium.net/temurin/releases/?version=17"


@dataclass
class StartupProgressWindow:
    process: subprocess.Popen | None = None

    def show(self, step: int, total: int, message: str) -> None:
        self.close()
        prompt = (
            f"Opening EOT Diff Tool\n\n"
            f"Step {step}/{total}\n"
            f"{message}\n\n"
            "Please wait..."
        )
        script = (
            f"display dialog {json.dumps(prompt)} "
            'with title "Launching" '
            'buttons {"Hide"} default button "Hide" '
            "giving up after 86400"
        )
        self.process = subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def close(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1.0)
        self.process = None


def _run_dialog(title: str, message: str, buttons: list[str], default_button: str) -> subprocess.CompletedProcess:
    button_list = "{" + ", ".join(json.dumps(button) for button in buttons) + "}"
    script = (
        f"display dialog {json.dumps(message)} "
        f"with title {json.dumps(title)} "
        f"buttons {button_list} "
        f"default button {json.dumps(default_button)}"
    )
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )


def _open_logs() -> None:
    subprocess.run(["open", str(LOG_DIR)], check=False)


def _show_error(title: str, message: str, allow_open_logs: bool = False) -> None:
    if allow_open_logs:
        result = _run_dialog(title, message, ["OK", "Open Logs"], "OK")
        if result.returncode == 0 and "button returned:Open Logs" in (result.stdout or ""):
            _open_logs()
        return

    _run_dialog(title, message, ["OK"], "OK")


def _ask_install(message: str) -> bool:
    prompt = message + "\n\nInstall missing prerequisites now?"
    result = _run_dialog("Install Prerequisites", prompt, ["Cancel", "Install"], "Install")
    return result.returncode == 0 and "button returned:Install" in (result.stdout or "")


def _show_install_failed_help(extra_message: str) -> None:
    prompt = (
        "Automatic install did not complete.\n\n"
        "Manual fix:\n"
        "1) Install Temurin/OpenJDK 17\n"
        "2) Verify with: java -version\n"
        "3) Relaunch the app\n\n"
        f"Details: {extra_message}\n\n"
        "Open Java 17 download page now?"
    )
    result = _run_dialog(
        "Install Failed",
        prompt,
        ["Cancel", "Open Download Page"],
        "Open Download Page",
    )
    if result.returncode == 0 and "button returned:Open Download Page" in (result.stdout or ""):
        subprocess.run(["open", JAVA17_URL], check=False)


def _reason_text(result: HealthCheckResult) -> str:
    messages = {
        "timeout": "Backend did not respond to /health in time.",
        "exited_early": "Backend exited before becoming healthy.",
        "port_bind_issue": "Backend could not bind a local port.",
        "missing_dependency": "Backend failed due to a missing dependency.",
    }
    return messages.get(result.reason, "Backend failed to start.")


def _show_backend_failure(
    handle: BackendHandle,
    result: HealthCheckResult,
    blocked_now: bool,
    blocked_seconds: int,
) -> None:
    block_note = ""
    if blocked_now:
        minutes = max(1, math.ceil(blocked_seconds / 60))
        block_note = (
            f"\n\nSafety pause enabled for {minutes} minute(s) due to repeated launch failures."
            "\nPlease wait, then relaunch."
        )

    exit_code_text = "none" if result.exit_code is None else str(result.exit_code)
    message = (
        f"{_reason_text(result)}\n\n"
        f"Session: {handle.session_id}\n"
        f"PID: {handle.pid}\n"
        f"Exit code: {exit_code_text}\n"
        f"Elapsed: {result.elapsed_seconds:.1f}s\n"
        f"Logs: {LOG_DIR}"
        f"{block_note}"
    )
    _show_error("Backend Error", message, allow_open_logs=True)


def _run_backend_mode(host: str, port: int, session_id: str) -> int:
    import uvicorn

    log_event(f"backend_mode_start session_id={session_id} host={host} port={port}")
    try:
        uvicorn.run("backend.app:app", host=host, port=port, log_level="info")
        log_event(f"backend_mode_exit session_id={session_id} code=0")
        return 0
    except KeyboardInterrupt:
        log_event(f"backend_mode_exit session_id={session_id} code=0 signal=interrupt")
        return 0
    except Exception as exc:  # pragma: no cover - defensive
        log_event(f"backend_mode_exception session_id={session_id} error={exc!r}")
        return 1


def _run_startup_sequence(
    *,
    show_progress: Callable[[int, int, str], None],
    close_progress: Callable[[], None],
    open_app: Callable[[str], None],
) -> tuple[int, BackendHandle | None]:
    handle: BackendHandle | None = None

    show_progress(1, 5, "Checking startup safety")
    blocked, remaining_seconds = check_temporary_block()
    if blocked:
        close_progress()
        minutes = max(1, math.ceil(remaining_seconds / 60))
        log_event(f"launch_blocked remaining_seconds={remaining_seconds}")
        _show_error(
            "Startup Paused",
            (
                "Startup is temporarily paused due to repeated launch failures.\n\n"
                f"Please wait about {minutes} minute(s) and relaunch.\n"
                f"Logs: {LOG_DIR}"
            ),
            allow_open_logs=True,
        )
        return 1, None

    show_progress(2, 5, "Checking prerequisites")
    prereq = check_prerequisites()
    if not prereq.ok:
        close_progress()
        if not _ask_install(prereq.message):
            _show_error(
                "Prerequisites Missing",
                "Cannot start app without Java 17+.\nPlease install prerequisites and relaunch.",
            )
            return 1, None

        post_install = install_prerequisites()
        if not post_install.ok:
            _show_install_failed_help(post_install.message)
            return 1, None
        show_progress(2, 5, "Prerequisites installed")

    last_failure: tuple[BackendHandle, HealthCheckResult] | None = None
    for attempt in (1, 2):
        show_progress(3, 5, f"Starting backend (attempt {attempt}/2)")
        handle = start_backend()
        log_event(
            f"backend_health_attempt session_id={handle.session_id} attempt={attempt} "
            f"port={handle.port} pid={handle.pid}"
        )
        show_progress(4, 5, f"Waiting for backend health (attempt {attempt}/2)")
        health = wait_for_health(handle, timeout_seconds=30)
        if health.ok:
            log_event(
                f"backend_healthy session_id={handle.session_id} attempt={attempt} "
                f"elapsed={health.elapsed_seconds:.2f}s"
            )
            record_launch_success()
            show_progress(5, 5, "Opening application window")
            open_app(handle.base_url)
            return 0, handle

        log_event(
            f"backend_unhealthy session_id={handle.session_id} attempt={attempt} "
            f"reason={health.reason} exit_code={health.exit_code} "
            f"elapsed={health.elapsed_seconds:.2f}s details={health.details!r}"
        )
        last_failure = (handle, health)
        stop_backend(handle)
        handle = None

        if attempt == 1:
            time.sleep(0.5)

    blocked_now, blocked_seconds = record_launch_failure()
    close_progress()
    if last_failure is not None:
        _show_backend_failure(
            handle=last_failure[0],
            result=last_failure[1],
            blocked_now=blocked_now,
            blocked_seconds=blocked_seconds,
        )
    else:
        _show_error(
            "Backend Error",
            f"Backend failed to become healthy.\nLogs: {LOG_DIR}",
            allow_open_logs=True,
        )
    return 1, None


def _run_ui_mode() -> int:
    ui_lock = acquire_ui_lock()
    if ui_lock is None:
        log_event("ui_lock_conflict already_running=true")
        _show_error(
            "App Already Running",
            "EOT Diff Tool is already running.\nClose the existing window before launching again.",
        )
        return 1

    handle: BackendHandle | None = None
    try:
        try:
            def run_with_splash(splash) -> int:
                nonlocal handle
                splash.update(0, 5, "Starting")
                rc, final_handle = _run_startup_sequence(
                    show_progress=lambda step, total, message: splash.update(step, total, message),
                    close_progress=splash.close,
                    open_app=splash.load_app,
                )
                handle = final_handle
                return rc

            return launch_with_startup_splash(run_with_splash)
        except Exception as exc:
            log_event(f"startup_splash_fallback error={exc!r}")
            progress = StartupProgressWindow()
            try:
                rc, final_handle = _run_startup_sequence(
                    show_progress=progress.show,
                    close_progress=progress.close,
                    open_app=lambda base_url: (progress.close(), launch_window(base_url)),
                )
                handle = final_handle
                return rc
            finally:
                progress.close()
    finally:
        stop_backend(handle)
        release_ui_lock(ui_lock)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--backend-mode", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18000)
    parser.add_argument("--session-id", default="unknown")
    parser.add_argument("--help", action="help")
    args, _ = parser.parse_known_args(argv)
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.backend_mode:
        return _run_backend_mode(host=args.host, port=args.port, session_id=args.session_id)

    return _run_ui_mode()


if __name__ == "__main__":
    sys.exit(main())
