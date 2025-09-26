#!/usr/bin/env python3
"""Stop hook - simplified function-based implementation."""
from __future__ import annotations

import argparse
import json
import sys

# Simple stdin parser (was utils.common_io)
def parse_stdin():
    import json, sys
    try:
        raw = sys.stdin.read().strip()
        return json.loads(raw) if raw else {}, None
    except Exception:
        return {}, None
from utils.constants import STOP
from utils.handler_result import HandlerResult


def handle_stop(context) -> "HandlerResult":  # type: ignore[name-defined]
    """Handle both Stop and SubagentStop events with same logic"""
    hr = HandlerResult()
    hr.audio_type = context.event_type  # Use event_type to handle both Stop/SubagentStop
    return hr


def handle_subagent_stop(context) -> "HandlerResult":  # type: ignore[name-defined]
    """Alias for handle_stop - same logic for both events"""
    return handle_stop(context)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable-audio", dest="enable_audio", action="store_true", help="Enable actual audio playback")
    ap.add_argument("--json-only", dest="json_only", action="store_true", help="Reserved for compatibility")
    args = ap.parse_args()

    payload, _ = parse_stdin()

    # Manual run audio + structured response for legacy Goal3 test
    audio_ctx = {"audioType": STOP, "enabled": False, "status": "skipped", "hookType": "Stop"}
    if args.enable_audio:
        from utils.audio_manager import AudioManager

        am = AudioManager()
        played, path, audio_ctx = am.play_audio_safe(STOP, enabled=True, additional_context={"source": "stop_cli"})
        audio_ctx = dict(audio_ctx or {})
        audio_ctx.update({"audioType": STOP, "enabled": True, "status": "played" if played else "skipped", "hookType": "Stop"})
    # Emit a minimal stderr marker for tests
    try:
        print("[Stop] invoked", file=sys.stderr)
    except Exception:
        pass
    response = {"continue": True, "additionalContext": {"audioContext": audio_ctx}}
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
