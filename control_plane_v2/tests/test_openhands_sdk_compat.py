from __future__ import annotations

import inspect
from pathlib import Path

from openhands.sdk import Conversation


def test_openhands_builder_avoids_unsupported_budget_keyword() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "miniverse"
        / "openhands_builder.py"
    ).read_text(encoding="utf-8")

    params = inspect.signature(Conversation).parameters
    if "max_budget_per_run" not in params:
        assert "max_budget_per_run=" not in source


def test_installed_sdk_supports_iteration_guard() -> None:
    params = inspect.signature(Conversation).parameters
    assert "max_iteration_per_run" in params
