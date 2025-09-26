#!/usr/bin/env python3
"""Notification hook - simplified function-based implementation.

This module provides a simple handler for the Notification event that does not
depend on BaseHook. It returns only the metadata needed by the dispatcher to
play audio and produce the JSON response.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Optional

# Simple stdin parser (was utils.common_io)
def parse_stdin():
    import json, sys
    try:
        raw = sys.stdin.read().strip()
        return json.loads(raw) if raw else {}, None
    except Exception:
        return {}, None
from utils.handler_result import HandlerResult
from utils.constants import NOTIFICATION


# Dispatcher-facing handler
def handle_notification(context) -> "HandlerResult":  # type: ignore[name-defined]
    hr = HandlerResult()
    hr.audio_type = NOTIFICATION
    # throttle window will be resolved by dispatcher defaults/config
    return hr


# Optional CLI for manual testing (plays audio directly when enabled)
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable-audio", dest="enable_audio", action="store_true", help="Enable actual audio playback")
    ap.add_argument("--json-only", dest="json_only", action="store_true", help="Reserved for compatibility")
    args = ap.parse_args()

    payload, _ = parse_stdin()

    # If audio is enabled, play the notification sound directly for manual runs
    audio_ctx = {"audioType": NOTIFICATION, "enabled": False, "status": "skipped", "hookType": "Notification"}
    if args.enable_audio:
        from utils.audio_manager import AudioManager

        am = AudioManager()
        played, path, ctx = am.play_audio_safe(NOTIFICATION, enabled=True, additional_context={"source": "notification_cli"})
        audio_ctx = dict(ctx or {})
        audio_ctx.update({"audioType": NOTIFICATION, "enabled": True, "status": "played" if played else "skipped", "hookType": "Notification"})

    # JSON output contract (legacy-compatible structured context)
    try:
        print(json.dumps({"continue": True, "additionalContext": {"audioContext": audio_ctx}}))
    except Exception:
        print("{\"continue\": true}")
    # Emit a minimal stderr marker for tests
    try:
        print("[Notification] invoked", file=sys.stderr)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
