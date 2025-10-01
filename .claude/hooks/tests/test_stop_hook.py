"""Tests for stop and subagent stop hook behaviour."""
from __future__ import annotations

from types import SimpleNamespace

from common_test_utils import run_hook
from utils.constants import STOP, SUBAGENT_STOP
import stop as stop_hook


def test_handle_stop_uses_event_audio(monkeypatch) -> None:
    """handle_stop should mirror the incoming event type for audio playback."""

    context = SimpleNamespace(event_type=STOP, payload={})
    result = stop_hook.handle_stop(context)

    assert result.audio_type == STOP
    assert result.continue_value is True


def test_handle_subagent_stop_aliases_stop() -> None:
    """The subagent hook reuses the core implementation."""

    context = SimpleNamespace(event_type=SUBAGENT_STOP, payload={})
    result = stop_hook.handle_subagent_stop(context)

    assert result.audio_type == SUBAGENT_STOP
    assert result.continue_value is True


def test_cli_outputs_continue_contract() -> None:
    """The CLI wrapper should emit a continue response and tag stderr."""

    payload = {"hookEventName": STOP, "status": "complete"}
    result = run_hook(".claude/hooks/stop.py", payload=payload, args=["--enable-audio"])

    assert result.returncode == 0
    response = result.json()
    assert response["continue"] is True
    assert "Stop" in result.stderr
