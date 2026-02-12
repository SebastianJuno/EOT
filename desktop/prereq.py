from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "EOTDiff"
CONFIG_PATH = APP_SUPPORT_DIR / "config.json"
LOG_DIR = Path.home() / "Library" / "Logs" / "EOTDiff"
LOG_PATH = LOG_DIR / "launcher.log"


@dataclass
class PrereqResult:
    ok: bool
    java_ok: bool
    java_version: str | None
    message: str


def _log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()} {message}\n"
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line)


def _write_config(java_ok: bool) -> None:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "prereq_checked_at": datetime.now(timezone.utc).isoformat(),
        "java_ok": java_ok,
        "last_version_seen": "0.6.0",
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_java_version(raw: str) -> str | None:
    match = re.search(r'"(\d+)(?:\.(\d+))?.*"', raw)
    if not match:
        return None
    major = match.group(1)
    minor = match.group(2) or "0"
    return f"{major}.{minor}"


def _java_check() -> tuple[bool, str | None, str]:
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, None, "Java runtime not found"

    output = f"{result.stdout}\n{result.stderr}".strip()
    version = _parse_java_version(output)
    if result.returncode != 0 or version is None:
        return False, None, "Unable to determine Java version"

    major = int(version.split(".")[0])
    if major < 17:
        return False, version, f"Java {version} found. Java 17+ required."
    return True, version, f"Java {version} OK"


def check_prerequisites() -> PrereqResult:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)

    java_ok, java_version, msg = _java_check()
    _write_config(java_ok)
    _log(f"check_prerequisites java_ok={java_ok} java_version={java_version} msg={msg}")

    return PrereqResult(
        ok=java_ok,
        java_ok=java_ok,
        java_version=java_version,
        message=msg,
    )


def install_prerequisites() -> PrereqResult:
    commands = [
        "if ! command -v brew >/dev/null 2>&1; then /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"; fi",
        "if [ -x /opt/homebrew/bin/brew ]; then eval \"$(/opt/homebrew/bin/brew shellenv)\"; elif [ -x /usr/local/bin/brew ]; then eval \"$(/usr/local/bin/brew shellenv)\"; fi",
        "brew install openjdk@17",
    ]
    shell_script = " && ".join(commands)
    bash_cmd = f"/bin/bash -lc {shlex.quote(shell_script)}"

    osa_expr = f"do shell script {json.dumps(bash_cmd)} with administrator privileges"
    install = subprocess.run(
        ["osascript", "-e", osa_expr],
        capture_output=True,
        text=True,
        check=False,
    )
    _log(
        "install_prerequisites "
        f"code={install.returncode} stdout={install.stdout.strip()} stderr={install.stderr.strip()}"
    )

    return check_prerequisites()
