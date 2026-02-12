from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from desktop.backend_runner import start_backend, stop_backend, wait_for_health
from desktop.prereq import check_prerequisites, install_prerequisites
from desktop.window import launch_window


def _show_error(title: str, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)
    root.destroy()


def _ask_install(message: str) -> bool:
    root = tk.Tk()
    root.withdraw()
    answer = messagebox.askyesno(
        "Install Prerequisites",
        f"{message}\n\nInstall missing prerequisites now?",
    )
    root.destroy()
    return bool(answer)


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
            _show_error(
                "Install Failed",
                "Automatic install did not complete successfully.\n"
                "Please install OpenJDK 17 manually and relaunch the app.",
            )
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
