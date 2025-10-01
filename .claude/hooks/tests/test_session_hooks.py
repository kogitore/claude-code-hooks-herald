"""Tests for session start and end hook helpers."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import session_end
import session_start
from utils import session_storage


@pytest.fixture
def session_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    """Redirect session storage and directories to a temporary sandbox."""

    logs_root = tmp_path / "logs"
    sessions_root = tmp_path / "sessions"
    logs_root.mkdir()
    sessions_root.mkdir()

    monkeypatch.setenv("CLAUDE_SESSION_ROOT", str(sessions_root))
    monkeypatch.setattr(session_storage, "_LOGS_ROOT", logs_root)
    monkeypatch.setattr(session_storage, "STATE_PATH", logs_root / "session_state.json")
    monkeypatch.setattr(session_storage, "EVENT_LOG_PATH", logs_root / "session_events.jsonl")
    monkeypatch.setattr(session_start, "_session_root_path", lambda session_id: sessions_root / session_id)
    monkeypatch.setattr(session_end, "_session_root_path", lambda session_id: sessions_root / session_id)
    monkeypatch.setattr(session_start, "_run_health_checks", lambda environment: (("sounds_directory_present",), ()))

    return {"logs_root": logs_root, "sessions_root": sessions_root}


def test_session_start_records_state_and_summary(session_env: dict[str, Path]) -> None:
    """Session start should persist state and return a structured summary."""

    payload = {
        "session_id": "sess-123",
        "user_id": "user-9",
        "start_time": "2025-09-22T00:00:00Z",
        "environment": {"working_directory": "/tmp"},
        "preferences": {"audio_enabled": True},
    }
    context = SimpleNamespace(payload=payload, decision_api=None)

    result = session_start.handle_session_start(context)

    assert result.audio_type == session_start.SESSION_START
    summary_json = result.response["hookSpecificOutput"]["additionalContext"]
    summary = json.loads(summary_json)
    assert summary["sessionId"] == "sess-123"

    state = json.loads(session_storage.STATE_PATH.read_text(encoding="utf-8"))
    assert state["sess-123"]["status"] == "active"

    events = session_storage.EVENT_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(events) == 1
    assert json.loads(events[0])["event"] == "session_start"


def test_session_end_updates_state_and_removes_resources(session_env: dict[str, Path]) -> None:
    """Session end should update state, remove resources, and log the event."""

    session_id = "sess-123"
    payload_start = {"session_id": session_id, "environment": {}}
    session_start.handle_session_start(SimpleNamespace(payload=payload_start, decision_api=None))

    target_dir = session_env["sessions_root"] / session_id / "artifacts"
    target_dir.mkdir(parents=True)
    (target_dir / "note.txt").write_text("temp", encoding="utf-8")

    payload_end = {
        "session_id": session_id,
        "end_time": "2025-09-22T01:00:00Z",
        "duration": 3600,
        "termination_reason": "normal",
        "resources_to_cleanup": ["artifacts"],
    }

    result = session_end.handle_session_end(SimpleNamespace(payload=payload_end, decision_api=None))

    assert result.audio_type == session_end.SESSION_END
    summary = json.loads(result.response["hookSpecificOutput"]["additionalContext"])
    assert "artifacts" in summary["removedResources"][0]
    assert not target_dir.exists()

    state = json.loads(session_storage.STATE_PATH.read_text(encoding="utf-8"))
    history = state[session_id]["history"]
    assert history[-1]["event"] == "session_end"

    events = session_storage.EVENT_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(events) == 2
    assert json.loads(events[-1])["event"] == "session_end"
