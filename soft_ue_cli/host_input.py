"""DPI-aware Windows host input for a live Weldborn PIE preview window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


PIE_WINDOW_TITLE = "WeldbornGame Preview"


class HostInputError(RuntimeError):
    """A host input request was unsafe or could not be sent."""


@dataclass(frozen=True)
class HostWindow:
    hwnd: int
    title: str


class WindowsInputBackend(Protocol):
    def window_at(self, x: int, y: int) -> HostWindow: ...

    def set_cursor_pos(self, x: int, y: int) -> bool: ...

    def click(self, button: str) -> bool: ...


def viewport_to_screen(
    viewport_local: tuple[float, float],
    viewport_origin_abs: tuple[float, float],
    slate_dpi_scale: float,
) -> tuple[float, float]:
    """Convert PIE viewport-local coordinates to absolute desktop pixels."""
    if slate_dpi_scale <= 0.0:
        raise HostInputError("slate_dpi_scale must be greater than zero")
    return (
        viewport_origin_abs[0] + viewport_local[0] * slate_dpi_scale,
        viewport_origin_abs[1] + viewport_local[1] * slate_dpi_scale,
    )


def screen_to_viewport(
    screen_abs: tuple[float, float],
    viewport_origin_abs: tuple[float, float],
    slate_dpi_scale: float,
) -> tuple[float, float]:
    """Convert absolute desktop pixels to PIE viewport-local coordinates."""
    if slate_dpi_scale <= 0.0:
        raise HostInputError("slate_dpi_scale must be greater than zero")
    return (
        (screen_abs[0] - viewport_origin_abs[0]) / slate_dpi_scale,
        (screen_abs[1] - viewport_origin_abs[1]) / slate_dpi_scale,
    )

def geometry_to_screen(
    projected_viewport_px: tuple[float, float],
    geometry: dict[str, object],
) -> tuple[float, float]:
    """Use the bridge's PIE viewport origin, never a window client origin."""
    raw_origin = geometry.get("pie_viewport_origin_abs")
    if not isinstance(raw_origin, (list, tuple)) or len(raw_origin) != 2:
        raise HostInputError("pie_viewport_origin_abs must contain two numbers")
    raw_scale = geometry.get("slate_dpi_scale")
    if not isinstance(raw_scale, (int, float)):
        raise HostInputError("slate_dpi_scale must be a number")
    return viewport_to_screen(
        projected_viewport_px,
        (float(raw_origin[0]), float(raw_origin[1])),
        float(raw_scale),
    )


class CtypesWindowsInputBackend:
    """Small user32 adapter. It is created only when input is sent."""

    _GA_ROOT = 2
    _MOUSE_FLAGS = {
        "left": (0x0002, 0x0004),
        "right": (0x0008, 0x0010),
    }

    def __init__(self) -> None:
        import ctypes
        import ctypes.wintypes as wintypes
        import os

        if os.name != "nt":
            raise HostInputError("host input is available only on Windows")
        self._ctypes = ctypes
        self._wintypes = wintypes
        self._user32 = ctypes.windll.user32
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                self._user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass

    def window_at(self, x: int, y: int) -> HostWindow:
        point = self._wintypes.POINT(x, y)
        hwnd = self._user32.WindowFromPoint(point)
        if not hwnd:
            return HostWindow(hwnd=0, title="")
        root = self._user32.GetAncestor(hwnd, self._GA_ROOT) or hwnd
        length = self._user32.GetWindowTextLengthW(root)
        buffer = self._ctypes.create_unicode_buffer(max(1, length + 1))
        self._user32.GetWindowTextW(root, buffer, len(buffer))
        return HostWindow(hwnd=int(root), title=buffer.value)

    def set_cursor_pos(self, x: int, y: int) -> bool:
        return bool(self._user32.SetCursorPos(x, y))

    def click(self, button: str) -> bool:
        if button not in self._MOUSE_FLAGS:
            raise HostInputError(f"unsupported mouse button: {button}")
        down, up = self._MOUSE_FLAGS[button]
        self._user32.mouse_event(down, 0, 0, 0, 0)
        self._user32.mouse_event(up, 0, 0, 0, 0)
        return True


def dispatch_click(
    screen_abs: tuple[float, float],
    *,
    button: str = "left",
    expected_title: str = PIE_WINDOW_TITLE,
    backend: WindowsInputBackend | None = None,
) -> dict[str, object]:
    """Send one click only when its desktop point belongs to Weldborn PIE."""
    target_x = round(screen_abs[0])
    target_y = round(screen_abs[1])
    input_backend = backend or CtypesWindowsInputBackend()
    window = input_backend.window_at(target_x, target_y)
    if not window.hwnd or expected_title not in window.title:
        title = window.title or "<none>"
        raise HostInputError(
            f"refusing host input: target HWND title '{title}' does not contain "
            f"'{expected_title}'"
        )
    if not input_backend.set_cursor_pos(target_x, target_y):
        raise HostInputError("SetCursorPos failed")
    if not input_backend.click(button):
        raise HostInputError("mouse input dispatch failed")
    return {
        "hwnd": window.hwnd,
        "title": window.title,
        "screen_abs": [target_x, target_y],
        "dispatched": True,
    }
