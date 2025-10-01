"""Tests for PostToolUse hook behaviour and audit logging."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import post_tool_use
from utils.constants import POST_TOOL_USE


class FakeDecision:
    """Test-friendly stand-in for DecisionResult."""

    def __init__(
        self,
        decision: str,
        blocked: bool,
        *,
        payload: dict[str, object] | None = None,
    ) -> None:
        base = payload or {}
        base.setdefault("decision", decision)
        base.setdefault("permissionDecision", decision)
        self.payload = base
        self.blocked = blocked

    def to_dict(self) -> dict[str, object]:
        return {**self.payload, "blocked": self.blocked}


def test_successful_tool_run_allows_and_logs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Successful executions should allow continuation and append an audit record."""

    class AllowAPI:
        def post_tool_use_decision(self, tool: str, result: dict[str, object]):
            return FakeDecision("allow", False, payload={"additionalContext": {}})

    audit_log = tmp_path / "tool_audit.jsonl"
    monkeypatch.setattr(post_tool_use, "AUDIT_LOG_PATH", audit_log)
    monkeypatch.setattr(post_tool_use, "DecisionAPI", AllowAPI)

    payload = {
        "tool": "bash",
        "result": {"success": True, "output": "finished"},
        "execution_time": 0.42,
    }
    context = SimpleNamespace(payload=payload, decision_api=None)
    result = post_tool_use.handle_post_tool_use(context)

    assert result.continue_value is True
    assert result.suppress_audio is True
    decision = result.decision_payload
    assert decision["decision"] == "allow"
    audit = decision["additionalContext"]
    assert audit["tool"] == "bash"
    assert audit["result"]["success"] is True

    log_entry = audit_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_entry) == 1
    assert json.loads(log_entry[0])["decision"] == "allow"


def test_failed_tool_run_blocks_and_flags_alerts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Failures should block continuation, trigger alerts, and request audio."""

    class BlockAPI:
        def post_tool_use_decision(self, tool: str, result: dict[str, object]):
            payload = {"additionalContext": {}}
            return FakeDecision("block", True, payload=payload)

    audit_log = tmp_path / "tool_audit.jsonl"
    monkeypatch.setattr(post_tool_use, "AUDIT_LOG_PATH", audit_log)
    monkeypatch.setattr(post_tool_use, "DecisionAPI", BlockAPI)

    payload = {
        "tool": "python",
        "result": {"success": False, "error": "Traceback...", "exit_code": 1},
    }
    context = SimpleNamespace(payload=payload, decision_api=None)
    result = post_tool_use.handle_post_tool_use(context)

    assert result.continue_value is False
    assert result.audio_type == POST_TOOL_USE
    decision = result.decision_payload
    assert decision["decision"] == "block"
    alerts = decision["additionalContext"]["result"]["alerts"]
    assert "error_detected" in alerts

    log_entry = json.loads(audit_log.read_text(encoding="utf-8").strip())
    assert log_entry["decision"] == "block"
