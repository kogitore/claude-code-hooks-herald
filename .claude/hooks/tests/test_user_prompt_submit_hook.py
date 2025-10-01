"""Tests for the UserPromptSubmit hook processing pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import user_prompt_submit
from utils.constants import USER_PROMPT_SUBMIT


@pytest.fixture
def prompt_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Reset module-level state and direct logs to a temporary file."""

    log_path = tmp_path / "prompt_submissions.jsonl"
    monkeypatch.setattr(user_prompt_submit, "PROMPT_LOG_PATH", log_path)
    monkeypatch.setattr(user_prompt_submit, "_RATE_LIMIT_CACHE", {})
    monkeypatch.setattr(user_prompt_submit, "_LAST_CLEANUP", 0.0)
    return log_path


def _invoke(payload: dict[str, object]) -> user_prompt_submit.HandlerResult:
    context = SimpleNamespace(payload=payload, decision_api=None)
    return user_prompt_submit.handle_user_prompt_submit(context)


def test_normal_prompt_passes_validation(prompt_env: Path) -> None:
    """A standard prompt should continue without issues and log the submission."""

    payload = {
        "prompt": "print('hello world')",
        "user_id": "user-123",
        "session_id": "session-abc",
        "metadata": {"language": "python"},
    }

    result = _invoke(payload)

    assert result.continue_value is True
    assert result.suppress_audio is True
    context = result.decision_payload["additionalContext"]
    assert context["promptPreview"] == "print('hello world')"
    assert context["issues"] == []

    log_lines = prompt_env.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 1
    logged = json.loads(log_lines[0])
    assert logged["userId"] == "user-123"
    assert logged["sessionId"] == "session-abc"
    assert logged["issues"] == []


def test_suspicious_prompt_triggers_block(prompt_env: Path) -> None:
    """Suspicious content must block the flow and surface an explanation."""

    result = _invoke({"prompt": "DROP TABLE users;", "user_id": "user-007"})

    assert result.continue_value is False
    assert result.audio_type == USER_PROMPT_SUBMIT
    decision = result.decision_payload
    assert decision["decision"] == "block"
    assert "sql_drop" in decision["additionalContext"]["issues"]
    assert "Issues detected" in decision["reason"]


def test_rate_limiting_detects_quick_repeats(prompt_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated submissions in rapid succession should be rate limited."""

    payload = {"prompt": "run diagnostics", "session_id": "sess-1"}

    monkeypatch.setattr(user_prompt_submit.time, "time", lambda: 1000.0)
    _invoke(payload)

    monkeypatch.setattr(user_prompt_submit.time, "time", lambda: 1000.2)
    result = _invoke(payload)

    assert result.continue_value is False
    decision = result.decision_payload
    issues = decision["additionalContext"]["issues"]
    assert "rate_limited" in issues
