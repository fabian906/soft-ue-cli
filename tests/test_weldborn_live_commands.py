"""Weldborn frame-settle command behavior tests."""

from __future__ import annotations

import argparse
import json

import pytest

from soft_ue_cli import weldborn_commands


def test_wait_dispatches_once_per_requested_frame(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        calls.append((name, arguments))
        return {"game_frame": len(calls)}

    monkeypatch.setattr(weldborn_commands, "_bridge_call", fake_call)
    weldborn_commands.cmd_wait_frames(argparse.Namespace(game=3, slate=2))

    assert calls == [("weldborn.wait.frames", {})] * 3
    assert json.loads(capsys.readouterr().out)["dispatches"] == 3


def test_palette_select_waits_before_reading_settled_state(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def fake_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
        calls.append(name)
        if name == "weldborn.palette.select":
            return {"ok": True, "mode": "placement"}
        if name == "weldborn.wait.frames":
            return {"ok": True, "game_frame": 42}
        return {"ok": True, "content_id": "equipment.test"}

    monkeypatch.setattr(weldborn_commands, "_bridge_call", fake_call)
    weldborn_commands.cmd_palette_select(argparse.Namespace(content_id="equipment.test"))

    assert calls == [
        "weldborn.palette.select",
        "weldborn.wait.frames",
        "weldborn.authoring.snapshot",
    ]
    assert json.loads(capsys.readouterr().out)["settled_snapshot"]["content_id"] == "equipment.test"
