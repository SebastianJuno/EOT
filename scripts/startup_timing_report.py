#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop.startup_timing import latest_elapsed_for


def _default_log_path() -> Path:
    return Path.home() / "Library" / "Logs" / "EOTDiff" / "launcher.log"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report latest desktop startup splash timing.")
    parser.add_argument("--log-path", type=Path, default=_default_log_path())
    parser.add_argument(
        "--max-ms",
        type=int,
        default=None,
        help="Fail with exit code 1 if latest splash_shown exceeds this threshold.",
    )
    args = parser.parse_args(argv)

    splash_ms = latest_elapsed_for("splash_shown", args.log_path)
    if splash_ms is None:
        print(f"No splash timing found in: {args.log_path}")
        return 2

    print(f"Latest splash_shown: {splash_ms} ms")

    if args.max_ms is not None and splash_ms > args.max_ms:
        print(f"FAIL: splash_shown {splash_ms} ms exceeds threshold {args.max_ms} ms")
        return 1

    if args.max_ms is not None:
        print(f"PASS: splash_shown {splash_ms} ms <= threshold {args.max_ms} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
