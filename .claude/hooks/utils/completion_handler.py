#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple


def process_completion(am, *, audio_key: str, enable: bool, throttle_key: str, window_seconds: int) -> Tuple[bool, Optional[Path], bool]:
    """Shared completion/levelup processing.

    Returns (played, path, throttled).
    - Uses am.should_throttle(throttle_key, window_seconds)
    - If not throttled, plays am.play_audio(audio_key, enabled=enable) and am.mark_emitted(throttle_key)
    - Never raises
    """
    try:
        throttled = am.should_throttle(throttle_key, window_seconds=window_seconds)
    except Exception:
        throttled = False

    played: bool = False
    path: Optional[Path] = am.resolve_file(audio_key)
    if not throttled:
        played, path = am.play_audio(audio_key, enabled=enable)
        try:
            am.mark_emitted(throttle_key)
        except Exception:
            pass
    return played, path, throttled

