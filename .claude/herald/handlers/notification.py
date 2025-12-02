#!/usr/bin/env python3
"""Notification hook implementation."""
from __future__ import annotations

import argparse
import json
import sys

from herald.utils.constants import NOTIFICATION
from herald.utils.handler_result import HandlerResult
from herald.utils.audio_manager import AudioManager


def handle_notification(context) -> HandlerResult:
    """Return a result instructing the dispatcher to play the notification tone."""
    result = HandlerResult()
    result.audio_type = context.event_type or NOTIFICATION
    return result


def _read_payload() -> dict[str, object]:
    """Read JSON payload from stdin, returning empty dict on failure."""
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def main() -> int:
    """Entry point for manual invocations."""
    parser = argparse.ArgumentParser(description="Claude Code Notification hook")
    parser.add_argument("--enable-audio", action="store_true",
                       help="Play the configured notification sound")
    parser.add_argument("--json-only", action="store_true",
                       help="Retained for compatibility; no behavioural impact")
    args = parser.parse_args()

    _payload = _read_payload()

    # Build audio context
    audio_context = {"audioType": NOTIFICATION, "enabled": False,
                    "status": "skipped", "hookType": "Notification"}

    if args.enable_audio:
        try:
            manager = AudioManager()
            played, _path, context = manager.play_audio_safe(
                NOTIFICATION, enabled=True,
                additional_context={"source": "notification_cli"}
            )
            audio_context.update({
                **context,
                "audioType": NOTIFICATION,
                "enabled": True,
                "status": "played" if played else "skipped",
                "hookType": "Notification",
            })
        except Exception:
            audio_context["reason"] = "audio_manager_unavailable"

    response = {"continue": True, "additionalContext": {"audioContext": audio_context}}

    try:
        print(json.dumps(response, ensure_ascii=False))
    except Exception:
        print("{\"continue\": true}")

    try:
        print("[Notification] invoked", file=sys.stderr)
    except OSError:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
