#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.comparison import compare_tasks
from backend.csv_import import parse_tasks_from_csv_bytes


DEFAULT_PATHS = [
    Path("/Users/sebastian.bujnowski/Documents/Test Programmes/C01_32HVR_Programme.csv"),
    Path("/Users/sebastian.bujnowski/Documents/Test Programmes/C02_32HVR_Programe_050925_.csv"),
    Path("/Users/sebastian.bujnowski/Documents/Test Programmes/C03_32HVR_Programe_09012026.csv"),
]


def _parse_one(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV file: {path}")
    tasks, diagnostics = parse_tasks_from_csv_bytes(
        path.read_bytes(),
        column_map={},
        allow_inference=True,
        return_diagnostics=True,
    )
    if not tasks:
        raise RuntimeError(f"No tasks parsed from {path}")
    return tasks, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-check CSV inference and compare flow against real programme exports."
    )
    parser.add_argument(
        "csv_paths",
        nargs="*",
        type=Path,
        help="Optional override paths. If omitted, uses the three default Test Programmes CSVs.",
    )
    args = parser.parse_args()
    paths = args.csv_paths or DEFAULT_PATHS

    parsed = []
    for path in paths:
        tasks, diagnostics = _parse_one(path)
        print(
            f"{path.name}: parsed={len(tasks)} synthetic_uid={diagnostics.synthetic_uid} "
            f"warnings={len(diagnostics.warnings)} skipped_duplicate_header_rows={diagnostics.skipped_duplicate_header_rows}"
        )
        parsed.append((path, tasks))

    if len(parsed) >= 2:
        for idx in range(len(parsed) - 1):
            left_path, left_tasks = parsed[idx]
            right_path, right_tasks = parsed[idx + 1]
            result = compare_tasks(left_tasks, right_tasks, include_baseline=False)
            if result.summary.total_left_leaf_tasks <= 0 or result.summary.total_right_leaf_tasks <= 0:
                raise RuntimeError(
                    f"Unexpected empty compare result for {left_path.name} -> {right_path.name}"
                )
            print(
                f"compare {left_path.name} -> {right_path.name}: "
                f"left_leaf={result.summary.total_left_leaf_tasks} "
                f"right_leaf={result.summary.total_right_leaf_tasks} changed={result.summary.changed_tasks}"
            )

    print("CSV smoke check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
