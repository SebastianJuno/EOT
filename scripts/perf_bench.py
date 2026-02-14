#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from time import perf_counter

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.comparison import compare_tasks
from backend.preview import PREVIEW_SESSIONS, build_preview_rows_response, create_preview_session
from backend.schemas import TaskRecord


@dataclass(frozen=True)
class Scenario:
    name: str
    kind: str
    offset: int = 0


SCENARIOS = [
    Scenario(name="compare_exact_names", kind="compare", offset=0),
    Scenario(name="compare_fallback_names", kind="compare", offset=1),
    Scenario(name="preview_rows_exact_names", kind="preview", offset=0),
]


def _build_tasks(n: int, *, right: bool, name_offset: int) -> list[TaskRecord]:
    base = date(2025, 1, 1)
    tasks: list[TaskRecord] = []
    for i in range(n):
        uid = (100_000 if right else 0) + i + 1
        if right:
            name = f"Task {i + name_offset:05d}"
        else:
            name = f"Task {i:05d}"
        start = base + timedelta(days=(i % 45) + (1 if right and (i % 4 == 0) else 0))
        finish = start + timedelta(days=2)
        tasks.append(
            TaskRecord(
                uid=uid,
                name=name,
                start=start,
                finish=finish,
                duration_minutes=1440,
                percent_complete=50,
                predecessors=[],
            )
        )
    return tasks


def _run_case(scenario: Scenario, n: int, repeats: int) -> dict:
    timings_ms: list[float] = []
    for _ in range(repeats):
        left = _build_tasks(n, right=False, name_offset=0)
        right = _build_tasks(n, right=True, name_offset=scenario.offset)

        t0 = perf_counter()
        if scenario.kind == "compare":
            compare_tasks(left, right, include_baseline=False)
        else:
            session = create_preview_session(
                file_kind=".csv",
                include_baseline=False,
                left_tasks=left,
                right_tasks=right,
            )
            build_preview_rows_response(session, include_summaries=False, offset=0, limit=200)
            PREVIEW_SESSIONS.clear()
        t1 = perf_counter()
        timings_ms.append(round((t1 - t0) * 1000, 3))

    return {
        "scenario": scenario.name,
        "size": n,
        "timings_ms": timings_ms,
        "median_ms": round(median(timings_ms), 3),
    }


def _key(row: dict) -> str:
    return f"{row['scenario']}:{row['size']}"


def _load_baseline(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("results", [])
    return {_key(row): float(row["median_ms"]) for row in rows}


def _format_report(results: list[dict], baseline: dict[str, float] | None) -> str:
    lines = ["scenario,size,median_ms,delta_vs_baseline_pct"]
    for row in results:
        delta = "n/a"
        if baseline is not None:
            base = baseline.get(_key(row))
            if base and base > 0:
                change = ((row["median_ms"] - base) / base) * 100
                delta = f"{change:.1f}%"
        lines.append(f"{row['scenario']},{row['size']},{row['median_ms']},{delta}")
    return "\n".join(lines)


def _has_regression(results: list[dict], baseline: dict[str, float], threshold_pct: float) -> list[str]:
    regressions: list[str] = []
    for row in results:
        base = baseline.get(_key(row))
        if not base or base <= 0:
            continue
        change = ((row["median_ms"] - base) / base) * 100
        if change > threshold_pct:
            regressions.append(
                f"{row['scenario']} size={row['size']} median {row['median_ms']}ms > baseline {base}ms ({change:.1f}%)"
            )
    return regressions


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark compare/preview performance and detect regressions.")
    parser.add_argument("--sizes", default="200,500,1000", help="Comma-separated dataset sizes.")
    parser.add_argument("--repeats", type=int, default=5, help="Runs per scenario+size.")
    parser.add_argument("--output", default="build/perf-latest.json", help="JSON report output path.")
    parser.add_argument("--baseline", default="config/perf-baseline.json", help="Baseline JSON path.")
    parser.add_argument(
        "--regression-threshold-pct",
        type=float,
        default=25.0,
        help="Allowed slowdown percent versus baseline before failure.",
    )
    parser.add_argument("--enforce", action="store_true", help="Exit non-zero when regressions exceed threshold.")
    args = parser.parse_args()

    sizes = [int(part.strip()) for part in args.sizes.split(",") if part.strip()]
    results: list[dict] = []
    for scenario in SCENARIOS:
        for size in sizes:
            results.append(_run_case(scenario, size, repeats=args.repeats))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "sizes": sizes,
            "repeats": args.repeats,
            "regression_threshold_pct": args.regression_threshold_pct,
        },
        "results": results,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    baseline_path = Path(args.baseline)
    baseline: dict[str, float] | None = None
    if baseline_path.exists():
        baseline = _load_baseline(baseline_path)

    print(_format_report(results, baseline))
    print(f"\nSaved report to: {output_path}")

    if args.enforce:
        if baseline is None:
            print(f"ERROR: Baseline file not found: {baseline_path}")
            return 2
        regressions = _has_regression(results, baseline, args.regression_threshold_pct)
        if regressions:
            print("\nRegression(s) detected:")
            for item in regressions:
                print(f"- {item}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
