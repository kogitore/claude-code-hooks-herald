#!/usr/bin/env python3
"""
Notification Hook (audio-only) — Official JSON schema compliant

Output policy (per Claude Code Hooks docs):
- Print ONLY a single JSON object to stdout using standard fields.
- Allowed fields used here: `continue` (true). No custom fields.
"""
from __future__ import annotations

import argparse
import hashlib
import json as _json
import sys
from utils.audio_manager import AudioManager
from utils.common_io import parse_stdin, generate_audio_notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable-audio", dest="enable_audio", action="store_true", help="Enable actual audio playback")
    ap.add_argument("--json-only", dest="json_only", action="store_true", help="Suppress any non-JSON stdout (telemetry stays on stderr)")
    args = ap.parse_args()

    payload, marker = parse_stdin()

    am = AudioManager()

    # Throttle: 30s for identical message content (if provided)
    throttle_key = "user_notification"
    msg = payload.get("message") if isinstance(payload, dict) else None
    if msg:
        throttle_key = f"user_notification:{hashlib.sha1(str(msg).encode()).hexdigest()[:12]}"

    throttled = am.should_throttle(throttle_key, window_seconds=30)
    played = False
    path = am.resolve_file("user_notification")
    if not throttled:
        played, path = am.play_audio("user_notification", enabled=args.enable_audio)
        am.mark_emitted(throttle_key)

    # Telemetry to stderr
    notes = generate_audio_notes(
        throttled=throttled,
        path=path,
        played=played,
        enabled=args.enable_audio,
        throttle_msg="Throttled (<=30s)",
    )
    try:
        print(f"[notification] audioPlayed={bool(played)} throttled={bool(throttled)} path={path} notes={notes}", file=sys.stderr)
    except Exception:
        pass

    # Output required JSON response per Claude Code Hooks specification
    response = {"continue": True}
    print(_json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
