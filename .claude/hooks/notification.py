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

from utils.common_io import parse_stdin
from utils.constants import NOTIFICATION


# Dispatcher-facing handler
def handle_notification(context) -> "HandlerResult":  # type: ignore[name-defined]
    from herald import HandlerResult  # local import to avoid circulars
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
    if args.enable_audio:
        from utils.audio_manager import AudioManager

        am = AudioManager()
        am.play_audio_safe(NOTIFICATION, enabled=True, additional_context={"source": "notification_cli"})

    # JSON output contract
    try:
        print(json.dumps({"continue": True}))
    except Exception:
        print("{\"continue\": true}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
