from __future__ import annotations

from pathlib import Path

from desktop.startup_timing import latest_elapsed_for, parse_startup_timing_events


def test_parse_startup_timing_events_extracts_elapsed_values() -> None:
    payload = (
        "2026-02-14T10:00:00Z startup_timing event=launch_entry elapsed_ms=0\n"
        "2026-02-14T10:00:01Z startup_timing event=splash_window_created elapsed_ms=120\n"
        "2026-02-14T10:00:01Z startup_timing event=splash_shown elapsed_ms=340\n"
    )
    events = parse_startup_timing_events(payload)
    assert [event.event for event in events] == [
        "launch_entry",
        "splash_window_created",
        "splash_shown",
    ]
    assert [event.elapsed_ms for event in events] == [0, 120, 340]


def test_latest_elapsed_for_returns_latest_event_value(tmp_path: Path) -> None:
    log_path = tmp_path / "launcher.log"
    log_path.write_text(
        "\n".join(
            [
                "2026-02-14 startup_timing event=splash_shown elapsed_ms=550",
                "2026-02-14 startup_timing event=splash_shown elapsed_ms=430",
            ]
        ),
        encoding="utf-8",
    )
    assert latest_elapsed_for("splash_shown", log_path) == 430


def test_latest_elapsed_for_returns_none_when_missing(tmp_path: Path) -> None:
    log_path = tmp_path / "launcher.log"
    log_path.write_text("2026-02-14 launch something_else\n", encoding="utf-8")
    assert latest_elapsed_for("splash_shown", log_path) is None
