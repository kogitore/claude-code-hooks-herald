"""Tests for the PreToolUse hook decision logic."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import pre_tool_use
from utils.constants import PRE_TOOL_USE


class FakeDecision:
    """Test double mimicking the minimal DecisionResult protocol."""

    def __init__(
        self,
        decision: str,
        blocked: bool,
        *,
        reason: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        base = payload or {}
        base.setdefault("decision", decision)
        base.setdefault("permissionDecision", decision)
        if reason:
            base.setdefault("permissionDecisionReason", reason)
            base.setdefault("reason", reason)
        self.payload = base
        self.blocked = blocked

    def to_dict(self) -> dict[str, object]:
        return {**self.payload, "blocked": self.blocked}


def test_safe_command_allows_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clean commands should be allowed and suppress audio feedback."""

    class AllowAPI:
        def pre_tool_use_decision(self, tool: str, tool_input: dict[str, object]):
            return FakeDecision("allow", False, reason="Command is safe")

    monkeypatch.setattr(pre_tool_use, "DecisionAPI", AllowAPI)

    payload = {"tool": "bash", "toolInput": {"command": "echo hello"}}
    context = SimpleNamespace(payload=payload, decision_api=None)
    result = pre_tool_use.handle_pre_tool_use(context)

    assert result.continue_value is True
    assert result.suppress_audio is True
    assert result.decision_payload["permissionDecision"] == "allow"


def test_dangerous_command_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dangerous commands should block execution and request audio alert."""

    class DenyAPI:
        def pre_tool_use_decision(self, tool: str, tool_input: dict[str, object]):
            return FakeDecision("deny", True, reason="Dangerous command detected")

    monkeypatch.setattr(pre_tool_use, "DecisionAPI", DenyAPI)

    payload = {"tool": "bash", "toolInput": {"command": "rm -rf /"}}
    context = SimpleNamespace(payload=payload, decision_api=None)
    result = pre_tool_use.handle_pre_tool_use(context)

    assert result.continue_value is False
    assert result.audio_type == PRE_TOOL_USE
    assert result.decision_payload["permissionDecision"] == "deny"


def test_decision_api_failure_triggers_manual_review(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the decision API fails, the hook should surface an ask decision.

    According to Claude Code official docs, "ask" decision should block execution
    (continue: false) and prompt the user for confirmation in the UI.
    This prevents dangerous operations from executing without user approval.
    """

    class FallbackAPI:
        def pre_tool_use_decision(self, tool: str, tool_input: dict[str, object]):
            raise RuntimeError("boom")

        def ask(self, message: str, *, event: str, additional_context: dict[str, object]):
            payload = {
                "additionalContext": additional_context,
                "permissionDecisionReason": message,
            }
            # "ask" decision should block execution until user confirms
            return FakeDecision("ask", blocked=True, reason=message, payload=payload)

    monkeypatch.setattr(pre_tool_use, "DecisionAPI", FallbackAPI)

    payload = {"tool": "bash", "tool_input": "{not-json"}
    context = SimpleNamespace(payload=payload, decision_api=None)
    result = pre_tool_use.handle_pre_tool_use(context)

    assert result.continue_value is False
    assert result.audio_type == PRE_TOOL_USE
    decision = result.decision_payload
    assert decision["permissionDecision"] == "ask"
    assert "invalid_tool_input_json" in decision["additionalContext"]["issues"]
