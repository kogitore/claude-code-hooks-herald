#!/usr/bin/env python3
"""
SubagentStop Hook (level-up, audio-only) — Official JSON schema compliant

Output policy (per Claude Code Hooks docs):
- Print ONLY a single JSON object to stdout using standard fields.
- Allowed fields used here: `continue` (true), optional `stopReason`.
- No custom shapes like hookSpecificOutput on stdout (prints telemetry to stderr).
"""
from __future__ import annotations

import argparse
import json as _json
import sys
from utils.common_io import parse_stdin, generate_audio_notes
from utils.audio_manager import AudioManager
from utils.completion_handler import process_completion


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable-audio", dest="enable_audio", action="store_true", help="Enable actual audio playback")
    ap.add_argument("--json-only", dest="json_only", action="store_true", help="Suppress any non-JSON stdout (telemetry stays on stderr)")
    args = ap.parse_args()

    # Parse optional stdin (ignored for control)
    payload, marker = parse_stdin()

    am = AudioManager()
    window_seconds = am.get_throttle_window("SubagentStop", 120)
    # Throttle window configurable via audio_config.json (default 120s)
    played, path, throttled = process_completion(
        am,
        audio_key="SubagentStop",
        enable=bool(args.enable_audio),
        throttle_key="SubagentStop",
        window_seconds=window_seconds,
    )

    # Telemetry to stderr
    notes = generate_audio_notes(
        throttled=throttled,
        path=path,
        played=played,
        enabled=bool(args.enable_audio),
        throttle_msg=f"Throttled (<= {window_seconds}s)",
    )
    try:
        print(f"[SubagentStop] audioPlayed={bool(played)} throttled={bool(throttled)} path={path} notes={notes}", file=sys.stderr)
    except Exception:
        pass

    # Output required JSON response per Claude Code Hooks specification
    response = {"continue": True}
    print(_json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
