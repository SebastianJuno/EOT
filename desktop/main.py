from __future__ import annotations

import json
import subprocess
import sys

from desktop.backend_runner import start_backend, stop_backend, wait_for_health
from desktop.prereq import check_prerequisites, install_prerequisites
from desktop.window import launch_window

JAVA17_URL = "https://adoptium.net/temurin/releases/?version=17"


def _show_error(title: str, message: str) -> None:
    script = (
        f"display dialog {json.dumps(message)} "
        f'with title {json.dumps(title)} buttons {{"OK"}} default button "OK"'
    )
    subprocess.run(["osascript", "-e", script], check=False)


def _ask_install(message: str) -> bool:
    prompt = message + "\n\nInstall missing prerequisites now?"
    script = (
        f"display dialog {json.dumps(prompt)} "
        'with title "Install Prerequisites" '
        'buttons {"Cancel", "Install"} default button "Install"'
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
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
    script = (
        f"display dialog {json.dumps(prompt)} "
        'with title "Install Failed" '
        'buttons {"Cancel", "Open Download Page"} default button "Open Download Page"'
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    if result.returncode == 0 and "button returned:Open Download Page" in (result.stdout or ""):
        subprocess.run(["open", JAVA17_URL], check=False)


def main() -> int:
    prereq = check_prerequisites()
    if not prereq.ok:
        if not _ask_install(prereq.message):
            _show_error(
                "Prerequisites Missing",
                "Cannot start app without Java 17+.\nPlease install prerequisites and relaunch.",
            )
            return 1

        post_install = install_prerequisites()
        if not post_install.ok:
            _show_install_failed_help(post_install.message)
            return 1

    handle = None
    try:
        handle = start_backend()
        if not wait_for_health(handle.base_url, timeout_seconds=30):
            _show_error("Backend Error", "Backend failed to become healthy in time.")
            return 1
        launch_window(handle.base_url)
        return 0
    finally:
        stop_backend(handle)


if __name__ == "__main__":
    sys.exit(main())
