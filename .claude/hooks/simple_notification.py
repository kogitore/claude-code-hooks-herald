#!/usr/bin/env python3
"""Simplified Notification hook (audio-only, JSON in/out)."""
import json
import sys
from utils.simple_audio_manager import SimpleAudioManager
from utils.simple_constants import NOTIFICATION


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    message = data.get("message") or data.get("text") or ""

    am = SimpleAudioManager()
    played, path, _ = am.play_audio_safe(NOTIFICATION, enabled=True)

    out = {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": NOTIFICATION,
            "additionalContext": f"Audio {'played' if played else 'skipped'}"
        }
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Silent failure: never break Claude Code
        print(json.dumps({"continue": True}))
        raise SystemExit(0)
