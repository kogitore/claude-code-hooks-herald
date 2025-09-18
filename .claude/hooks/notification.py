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

    # Throttle window configurable via audio_config.json (default 30s)
    throttle_key = "Notification"
    msg = payload.get("message") if isinstance(payload, dict) else None
    if msg:
        throttle_key = f"Notification:{hashlib.sha1(str(msg).encode()).hexdigest()[:12]}"

    window_seconds = am.get_throttle_window("Notification", 30)
    throttled = am.should_throttle(throttle_key, window_seconds=window_seconds)
    played = False
    path = am.resolve_file("Notification")
    if not throttled:
        played, path = am.play_audio("Notification", enabled=args.enable_audio)
        am.mark_emitted(throttle_key)

    # Telemetry to stderr
    notes = generate_audio_notes(
        throttled=throttled,
        path=path,
        played=played,
        enabled=args.enable_audio,
        throttle_msg=f"Throttled (<= {window_seconds}s)",
    )
    try:
        print(f"[Notification] audioPlayed={bool(played)} throttled={bool(throttled)} path={path} notes={notes}", file=sys.stderr)
    except Exception:
        pass

    # Output required JSON response per Claude Code Hooks specification
    response = {"continue": True}
    print(_json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
