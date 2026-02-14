from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable

SPLASH_HTML = """
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <style>
      :root {
        --bg-a: #f8f5ef;
        --bg-b: #efe8dc;
        --card: rgba(255, 255, 255, 0.92);
        --ink: #191813;
        --muted: #5f5a50;
        --line: #dad3c7;
        --fill-a: #0e6ba8;
        --fill-b: #2b9348;
      }
      * { box-sizing: border-box; }
      html, body { width: 100%; height: 100%; margin: 0; }
      body {
        display: grid;
        place-items: center;
        font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif;
        color: var(--ink);
        background: radial-gradient(circle at 20% 15%, var(--bg-a), var(--bg-b));
      }
      .card {
        width: min(500px, 86vw);
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 16px;
        box-shadow: 0 16px 44px rgba(31, 28, 20, 0.14);
        padding: 24px 22px 20px;
      }
      .label {
        margin: 0 0 6px;
        font-size: 12px;
        color: var(--muted);
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      h1 {
        margin: 0 0 8px;
        font-size: 24px;
        font-weight: 600;
      }
      .detail {
        margin: 0 0 14px;
        min-height: 20px;
        color: var(--muted);
      }
      .track {
        height: 4px;
        border-radius: 999px;
        background: #e6e1d7;
        overflow: hidden;
      }
      .fill {
        width: 0%;
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, var(--fill-a), var(--fill-b));
        transition: width 180ms ease;
      }
      .pct {
        margin: 10px 0 0;
        text-align: right;
        font-size: 12px;
        color: #4e493f;
      }
    </style>
  </head>
  <body>
    <div class=\"card\">
      <p class=\"label\">Launching</p>
      <h1 id=\"stage\">Starting</h1>
      <p id=\"detail\" class=\"detail\">Preparing application startup.</p>
      <div class=\"track\" role=\"progressbar\" aria-valuemin=\"0\" aria-valuemax=\"100\" aria-valuenow=\"0\">
        <div id=\"fill\" class=\"fill\"></div>
      </div>
      <p id=\"pct\" class=\"pct\">0%</p>
    </div>
    <script>
      window.__setStartupProgress = function (pct, stage, detail) {
        var value = Math.max(0, Math.min(100, Number(pct || 0)));
        var stageEl = document.getElementById('stage');
        var detailEl = document.getElementById('detail');
        var fillEl = document.getElementById('fill');
        var pctEl = document.getElementById('pct');
        if (stageEl) stageEl.textContent = stage || 'Starting';
        if (detailEl) detailEl.textContent = detail || '';
        if (fillEl) fillEl.style.width = value + '%';
        if (pctEl) pctEl.textContent = Math.round(value) + '%';
      };
    </script>
  </body>
</html>
"""


_WEBVIEW_MODULE = None
_LAUNCH_SCREEN = None


def _webview():
    global _WEBVIEW_MODULE
    if _WEBVIEW_MODULE is None:
        import webview as imported_webview  # type: ignore[import-not-found]

        _WEBVIEW_MODULE = imported_webview
    return _WEBVIEW_MODULE


class _ScreenRef:
    def __init__(self, frame) -> None:
        self.frame = frame


def _point_in_frame(point, frame) -> bool:
    left = float(frame.origin.x)
    bottom = float(frame.origin.y)
    right = left + float(frame.size.width)
    top = bottom + float(frame.size.height)
    return left <= float(point.x) < right and bottom <= float(point.y) < top


def _detect_active_launch_screen():
    if sys.platform != "darwin":
        return None
    try:
        import AppKit  # type: ignore[import-not-found]

        pointer = AppKit.NSEvent.mouseLocation()
        for ns_screen in AppKit.NSScreen.screens():
            frame = ns_screen.frame()
            if _point_in_frame(pointer, frame):
                return _ScreenRef(frame)

        main_screen = AppKit.NSScreen.mainScreen()
        if main_screen is not None:
            return _ScreenRef(main_screen.frame())
    except Exception:
        return None
    return None


def _launch_screen():
    global _LAUNCH_SCREEN
    if _LAUNCH_SCREEN is None:
        _LAUNCH_SCREEN = _detect_active_launch_screen()
    return _LAUNCH_SCREEN


def _log_startup_timing(event: str, started_at: float | None = None) -> None:
    try:
        from desktop.prereq import log_event

        message = f"startup_timing event={event}"
        if started_at is not None:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000.0)
            message += f" elapsed_ms={elapsed_ms}"
        log_event(message)
    except Exception:
        # Startup logging should never block UI startup.
        pass


class StartupSplashWindow:
    def __init__(self, startup_t0: float | None = None) -> None:
        self._startup_t0 = startup_t0
        self.window = _webview().create_window(
            title="Launching EOT Diff Tool",
            html=SPLASH_HTML,
            width=620,
            height=420,
            min_size=(560, 360),
            resizable=True,
            screen=_launch_screen(),
        )
        if self._startup_t0 is not None:
            self.window.events.shown += lambda: _log_startup_timing("splash_shown", self._startup_t0)

    def update(self, step: int, total: int, stage: str, detail: str = "") -> None:
        pct = 0.0
        if total > 0:
            pct = max(0.0, min(100.0, (float(step) / float(total)) * 100.0))
        script = (
            f"window.__setStartupProgress({pct}, {json.dumps(stage)}, {json.dumps(detail)});"
        )
        try:
            self.window.evaluate_js(script)
        except Exception:
            # The webview may still be initializing; startup should continue.
            pass

    def load_app(self, base_url: str) -> None:
        if self._startup_t0 is not None:
            _log_startup_timing("app_url_load", self._startup_t0)
        self.window.load_url(base_url)
        self._expand_for_app()

    def _expand_for_app(self) -> None:
        if sys.platform == "darwin":
            launch_screen = _launch_screen()
            frame = getattr(launch_screen, "frame", None)
            if frame is not None:
                width = int(getattr(frame.size, "width", 1400))
                height = int(getattr(frame.size, "height", 900))
                try:
                    move = getattr(self.window, "move", None)
                    if callable(move):
                        move(0, 0)
                except Exception:
                    pass
                try:
                    resize = getattr(self.window, "resize", None)
                    if callable(resize):
                        resize(width, height)
                        return
                except Exception:
                    pass

        try:
            maximize = getattr(self.window, "maximize", None)
            if callable(maximize):
                maximize()
                return
        except Exception:
            pass

        try:
            resize = getattr(self.window, "resize", None)
            if callable(resize):
                resize(1400, 900)
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass


def launch_with_startup_splash(run_startup: Callable[[StartupSplashWindow], int]) -> int:
    startup_t0 = time.perf_counter()
    _log_startup_timing("launch_entry", startup_t0)
    splash = StartupSplashWindow(startup_t0=startup_t0)
    _log_startup_timing("splash_window_created", startup_t0)
    result: dict[str, int] = {"code": 1}

    def worker() -> None:
        code = 1
        try:
            splash.update(0, 5, "Starting", "Preparing application startup")
            code = run_startup(splash)
        finally:
            result["code"] = code
            if code != 0:
                splash.close()

    _webview().start(worker)
    return result["code"]


def launch_window(base_url: str) -> None:
    window = _webview().create_window(
        title="EOT Diff Tool",
        url=base_url,
        width=1400,
        height=900,
        min_size=(1000, 700),
        screen=_launch_screen(),
    )
    _webview().start()
