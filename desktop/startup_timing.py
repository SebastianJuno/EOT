from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TIMING_RE = re.compile(
    r"startup_timing event=(?P<event>[a-z_]+)(?: elapsed_ms=(?P<elapsed_ms>\d+))?"
)


@dataclass(frozen=True)
class StartupTimingEvent:
    event: str
    elapsed_ms: int | None


def parse_startup_timing_events(log_text: str) -> list[StartupTimingEvent]:
    events: list[StartupTimingEvent] = []
    for line in log_text.splitlines():
        match = _TIMING_RE.search(line)
        if not match:
            continue
        elapsed = match.group("elapsed_ms")
        events.append(
            StartupTimingEvent(
                event=match.group("event"),
                elapsed_ms=int(elapsed) if elapsed is not None else None,
            )
        )
    return events


def latest_elapsed_for(event_name: str, log_path: Path) -> int | None:
    if not log_path.exists():
        return None
    try:
        payload = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    latest: int | None = None
    for event in parse_startup_timing_events(payload):
        if event.event != event_name or event.elapsed_ms is None:
            continue
        latest = event.elapsed_ms
    return latest
