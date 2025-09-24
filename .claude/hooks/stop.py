#!/usr/bin/env python3
"""Stop hook - simplified function-based implementation."""
from __future__ import annotations

import argparse
import json
import sys

from utils.common_io import parse_stdin
from utils.constants import STOP


def handle_stop(context) -> "HandlerResult":  # type: ignore[name-defined]
    from herald import HandlerResult  # local import to avoid circulars
    hr = HandlerResult()
    hr.audio_type = STOP
    return hr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable-audio", dest="enable_audio", action="store_true", help="Enable actual audio playback")
    ap.add_argument("--json-only", dest="json_only", action="store_true", help="Reserved for compatibility")
    args = ap.parse_args()

    payload, _ = parse_stdin()

    # Manual run audio
    if args.enable_audio:
        from utils.audio_manager import AudioManager

        am = AudioManager()
        am.play_audio_safe(STOP, enabled=True, additional_context={"source": "stop_cli"})

    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
