"""Windows host-input contract tests for Weldborn live PIE debugging."""

from __future__ import annotations

import pytest

from soft_ue_cli.host_input import (
    HostInputError,
    HostWindow,
    geometry_to_screen,
    dispatch_click,
    screen_to_viewport,
    viewport_to_screen,
)


class FakeWindowsBackend:
    def __init__(self, window: HostWindow) -> None:
        self.window = window
        self.cursor_positions: list[tuple[int, int]] = []
        self.click_count = 0

    def window_at(self, x: int, y: int) -> HostWindow:
        return self.window

    def set_cursor_pos(self, x: int, y: int) -> bool:
        self.cursor_positions.append((x, y))
        return True

    def click(self, button: str) -> bool:
        self.click_count += 1
        return button == "left"


def test_host_input_round_trip_applies_slate_dpi_scale() -> None:
    viewport_origin = (240.0, 180.0)
    projected = (320.5, 170.25)
    scale = 1.5

    screen = viewport_to_screen(projected, viewport_origin, scale)

    assert screen == pytest.approx((720.75, 435.375))
    assert screen_to_viewport(screen, viewport_origin, scale) == pytest.approx(projected)


def test_host_input_uses_pie_viewport_origin_not_window_client_origin() -> None:
    geometry = {
        "pie_viewport_origin_abs": [132.0, 196.0],
        "window_client_origin_abs": [120.0, 150.0],
        "slate_dpi_scale": 1.0,
    }
    projected = (40.0, 60.0)

    screen = geometry_to_screen(projected, geometry)

    assert screen == pytest.approx((172.0, 256.0))
    assert screen != pytest.approx((160.0, 210.0))


def test_host_input_refuses_wrong_window_without_dispatch() -> None:
    backend = FakeWindowsBackend(HostWindow(hwnd=91, title="Unreal Editor"))

    with pytest.raises(HostInputError, match="WeldbornGame Preview"):
        dispatch_click((440.0, 320.0), backend=backend)

    assert backend.cursor_positions == []
    assert backend.click_count == 0


def test_host_input_result_names_target_window_and_delivery() -> None:
    backend = FakeWindowsBackend(
        HostWindow(hwnd=237, title="WeldbornGame Preview [NetMode: Standalone]")
    )

    result = dispatch_click((440.4, 320.6), backend=backend)

    assert result == {
        "hwnd": 237,
        "title": "WeldbornGame Preview [NetMode: Standalone]",
        "screen_abs": [440, 321],
        "dispatched": True,
    }
