from __future__ import annotations

import webview


def launch_window(base_url: str) -> None:
    window = webview.create_window(
        title="EOT Diff Tool",
        url=base_url,
        width=1400,
        height=900,
        min_size=(1000, 700),
    )
    webview.start()
