from __future__ import annotations

from types import SimpleNamespace

import desktop.window as desktop_window


class _WindowWithMaximize:
    def __init__(self):
        self.loaded_urls: list[str] = []
        self.maximized = 0
        self.resized: list[tuple[int, int]] = []
        self.moved: list[tuple[int, int]] = []

    def load_url(self, base_url: str) -> None:
        self.loaded_urls.append(base_url)

    def maximize(self) -> None:
        self.maximized += 1

    def resize(self, width: int, height: int) -> None:
        self.resized.append((width, height))

    def move(self, x: int, y: int) -> None:
        self.moved.append((x, y))


class _WindowWithoutMaximize:
    def __init__(self):
        self.loaded_urls: list[str] = []
        self.resized: list[tuple[int, int]] = []
        self.destroyed = 0
        self.moved: list[tuple[int, int]] = []

    def load_url(self, base_url: str) -> None:
        self.loaded_urls.append(base_url)

    def resize(self, width: int, height: int) -> None:
        self.resized.append((width, height))

    def move(self, x: int, y: int) -> None:
        self.moved.append((x, y))

    def destroy(self) -> None:
        self.destroyed += 1


def _fake_screen(width: int, height: int):
    return SimpleNamespace(
        frame=SimpleNamespace(
            origin=SimpleNamespace(x=0, y=0),
            size=SimpleNamespace(width=width, height=height),
        )
    )


def test_splash_load_app_fills_launch_screen_on_macos(monkeypatch):
    fake_window = _WindowWithMaximize()
    monkeypatch.setattr(desktop_window.sys, "platform", "darwin")
    monkeypatch.setattr(desktop_window, "_launch_screen", lambda: _fake_screen(1728, 1117))
    monkeypatch.setattr(
        desktop_window,
        "_webview",
        lambda: SimpleNamespace(create_window=lambda **_kwargs: fake_window),
    )

    splash = desktop_window.StartupSplashWindow()
    splash.load_app("http://127.0.0.1:19000")

    assert fake_window.loaded_urls == ["http://127.0.0.1:19000"]
    assert fake_window.moved == [(0, 0)]
    assert fake_window.resized == [(1728, 1117)]
    assert fake_window.maximized == 0


def test_splash_load_app_maximizes_when_screen_data_missing(monkeypatch):
    fake_window = _WindowWithMaximize()
    monkeypatch.setattr(desktop_window.sys, "platform", "darwin")
    monkeypatch.setattr(desktop_window, "_launch_screen", lambda: None)
    monkeypatch.setattr(
        desktop_window,
        "_webview",
        lambda: SimpleNamespace(create_window=lambda **_kwargs: fake_window),
    )

    splash = desktop_window.StartupSplashWindow()
    splash.load_app("http://127.0.0.1:19001")

    assert fake_window.loaded_urls == ["http://127.0.0.1:19001"]
    assert fake_window.maximized == 1
    assert fake_window.moved == []
    assert fake_window.resized == []


def test_launch_with_startup_splash_runs_single_flow(monkeypatch):
    recorded_updates: list[tuple[int, int, str, str]] = []
    fake_window = _WindowWithoutMaximize()

    class _FakeSplash(desktop_window.StartupSplashWindow):
        def __init__(self, startup_t0=None):
            self._startup_t0 = startup_t0
            self.window = fake_window

        def update(self, step: int, total: int, stage: str, detail: str = "") -> None:
            recorded_updates.append((step, total, stage, detail))

    monkeypatch.setattr(desktop_window, "_log_startup_timing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(desktop_window, "StartupSplashWindow", _FakeSplash)
    monkeypatch.setattr(desktop_window, "_webview", lambda: SimpleNamespace(start=lambda worker: worker()))

    rc = desktop_window.launch_with_startup_splash(lambda splash: (splash.update(1, 5, "Checking"), 0)[1])

    assert rc == 0
    assert recorded_updates[0][0:3] == (0, 5, "Starting")
    assert recorded_updates[1][0:3] == (1, 5, "Checking")


def test_splash_window_uses_launch_screen(monkeypatch):
    fake_window = _WindowWithoutMaximize()
    launch_screen = object()
    captured = {}

    def _create_window(**kwargs):
        captured.update(kwargs)
        return fake_window

    monkeypatch.setattr(desktop_window, "_launch_screen", lambda: launch_screen)
    monkeypatch.setattr(
        desktop_window,
        "_webview",
        lambda: SimpleNamespace(create_window=_create_window),
    )

    desktop_window.StartupSplashWindow()

    assert captured["screen"] is launch_screen


def test_launch_window_uses_launch_screen(monkeypatch):
    launch_screen = object()
    captured = {}

    def _create_window(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(desktop_window, "_launch_screen", lambda: launch_screen)
    monkeypatch.setattr(
        desktop_window,
        "_webview",
        lambda: SimpleNamespace(create_window=_create_window, start=lambda: None),
    )

    desktop_window.launch_window("http://127.0.0.1:19002")

    assert captured["screen"] is launch_screen
