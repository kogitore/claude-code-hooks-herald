#!/usr/bin/env python3
"""Stop hook leveraging BaseHook."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Optional

from utils.base_hook import BaseHook, HookExecutionResult
from utils.common_io import parse_stdin
from utils.constants import STOP


class StopHook(BaseHook):
    default_audio_event = STOP
    default_throttle_seconds = 120

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._last_payload: Dict[str, object] = {}

    def execute(self, data: Optional[Dict[str, object]], **kwargs) -> HookExecutionResult:  # type: ignore[override]
        self._last_payload = data or {}
        result = super().execute(data, **kwargs)  # type: ignore[arg-type]
        result.payload.clear()
        return result

    def validate_input(self, data: Dict[str, object]) -> bool:
        return isinstance(data, dict)

    def process(self, data: Dict[str, object]) -> Dict[str, object]:
        return {}

    def handle_error(self, error: Exception) -> Dict[str, object]:
        return {}

    def _default_throttle_key(self, audio_event: str, result: HookExecutionResult) -> str:  # type: ignore[override]
        marker = self._last_payload.get("marker")
        if isinstance(marker, str) and marker.strip():
            return f"{audio_event}:{marker}"
        return super()._default_throttle_key(audio_event, result)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable-audio", dest="enable_audio", action="store_true", help="Enable actual audio playback")
    ap.add_argument("--json-only", dest="json_only", action="store_true", help="Reserved for compatibility")
    args = ap.parse_args()

    payload, _ = parse_stdin()
    hook = StopHook()
    result = hook.execute(payload, enable_audio=bool(args.enable_audio))

    try:
        print(
            f"[Stop] audioPlayed={result.audio_played} throttled={result.throttled} "
            f"path={result.audio_path} notes={result.notes}",
            file=sys.stderr,
        )
    except Exception:
        pass

    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
