from __future__ import annotations

import json
from collections.abc import Callable

import webview

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


class StartupSplashWindow:
    def __init__(self) -> None:
        self.window = webview.create_window(
            title="Launching EOT Diff Tool",
            html=SPLASH_HTML,
            width=620,
            height=420,
            min_size=(560, 360),
            resizable=False,
        )

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
        self.window.load_url(base_url)

    def close(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass


def launch_with_startup_splash(run_startup: Callable[[StartupSplashWindow], int]) -> int:
    splash = StartupSplashWindow()
    result: dict[str, int] = {"code": 1}

    def worker() -> None:
        code = 1
        try:
            code = run_startup(splash)
        finally:
            result["code"] = code
            if code != 0:
                splash.close()

    webview.start(worker)
    return result["code"]


def launch_window(base_url: str) -> None:
    window = webview.create_window(
        title="EOT Diff Tool",
        url=base_url,
        width=1400,
        height=900,
        min_size=(1000, 700),
    )
    webview.start()
