"""Log bookmark and cursor contract tests for Weldborn live debugging."""

from __future__ import annotations

import pytest

from soft_ue_cli.weldborn_commands import WeldbornCommandError, build_log_since_arguments


def test_log_since_rejects_missing_cursor() -> None:
    with pytest.raises(WeldbornCommandError, match="cursor"):
        build_log_since_arguments("", categories=["authoring"])


def test_log_since_forwards_cursor_and_category_filter() -> None:
    arguments = build_log_since_arguments(
        "1842",
        categories=["authoring", "sim", "objective"],
    )

    assert arguments == {
        "lines": 0,
        "since": "1842",
        "category": ["authoring", "sim", "objective"],
    }
