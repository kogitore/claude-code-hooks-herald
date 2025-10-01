"""Tests covering the notification hook entrypoints."""
from __future__ import annotations

from types import SimpleNamespace

from common_test_utils import run_hook
from utils.constants import NOTIFICATION
import notification


def test_handler_sets_notification_audio_type() -> None:
    """The handler should request the notification audio channel."""

    context = SimpleNamespace(event_type=NOTIFICATION, payload={})
    result = notification.handle_notification(context)

    assert result.audio_type == NOTIFICATION
    assert result.continue_value is True


def test_cli_emits_continue_response() -> None:
    """CLI execution returns a JSON envelope and logs the marker to stderr."""

    payload = {"hookEventName": NOTIFICATION, "message": "ping"}
    result = run_hook(".claude/hooks/notification.py", payload=payload, args=["--enable-audio"])

    assert result.returncode == 0
    response = result.json()
    assert response["continue"] is True
    assert "Notification" in result.stderr
