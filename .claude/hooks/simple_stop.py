#!/usr/bin/env python3
"""Simplified Stop and SubagentStop hooks (audio-only)."""
import json
import sys
from utils.simple_audio_manager import SimpleAudioManager
from utils.simple_constants import STOP, SUBAGENT_STOP


def _handle(event_name: str) -> None:
    try:
        _ = json.load(sys.stdin)
    except Exception:
        pass
    am = SimpleAudioManager()
    played, path, _ = am.play_audio_safe(event_name, enabled=True)
    out = {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": f"Audio {'played' if played else 'skipped'}"
        }
    }
    print(json.dumps(out))


def main() -> int:
    # Determine which event to handle based on argv[1] fallback or default to Stop
    event = STOP
    if len(sys.argv) > 1 and sys.argv[1] in {STOP, SUBAGENT_STOP}:
        event = sys.argv[1]
    _handle(event)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({"continue": True}))
        raise SystemExit(0)
