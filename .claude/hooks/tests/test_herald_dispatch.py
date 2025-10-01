"""Integration tests for the herald dispatcher."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import herald
import post_tool_use
from utils.constants import POST_TOOL_USE, STOP


def test_unknown_event_defaults_to_continue() -> None:
    """Unregistered events should not block execution."""

    assert herald.dispatch("Unregistered", {}) == {"continue": True}


def test_stop_event_flows_through_dispatch() -> None:
    """The stop handler should execute via the dispatcher return path."""

    response = herald.dispatch(STOP, {"status": "done"})
    assert response["continue"] is True


def test_post_tool_use_integration_injects_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dispatcher should surface additional context provided by handlers."""

    class AllowAPI:
        def post_tool_use_decision(self, tool: str, result: dict[str, object]):
            payload = {"additionalContext": {}}
            return SimpleNamespace(payload=payload, blocked=False, to_dict=lambda: {"decision": "allow", **payload})

    monkeypatch.setattr(post_tool_use, "DecisionAPI", AllowAPI)

    payload = {"tool": "bash", "result": {"success": True, "output": "ok"}}
    response = herald.dispatch(POST_TOOL_USE, payload)

    assert response["continue"] is True
    hook_output = response["hookSpecificOutput"]
    assert hook_output["hookEventName"] == POST_TOOL_USE
    assert json.loads(hook_output["additionalContext"]) ["tool"] == "bash"
