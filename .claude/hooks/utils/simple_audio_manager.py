#!/usr/bin/env python3
"""Simple, self-contained audio manager for hooks (no external deps).

Goals:
- Tiny (<50 lines), robust, and silent on failure
- Map event names to .wav files from .claude/sounds
- Provide basic throttle helpers used by hooks
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Optional, Tuple


SOUNDS_DIR = Path(__file__).resolve().parents[2] / "sounds"
_last_emitted: Dict[str, float] = {}


class SimpleAudioManager:
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or SOUNDS_DIR

    def resolve(self, event: str) -> Optional[Path]:
        if not event:
            return None
        for name in (f"{event}.wav", f"{event.lower()}.wav"):
            p = self.base_dir / name
            if p.exists():
                return p
        return None

    def play_audio_safe(self, event: str, enabled: bool = True) -> Tuple[bool, Optional[Path], Dict[str, str]]:
        try:
            if not enabled:
                return False, None, {"reason": "audio-disabled"}
            path = self.resolve(event)
            if not path:
                return False, None, {"reason": "audio-not-found"}
            # Delegate actual playing to 'afplay' on macOS; silent if missing
            import subprocess

            subprocess.Popen(["afplay", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, path, {}
        except Exception:
            return False, None, {"reason": "audio-error"}

    # Minimal throttling helpers
    def should_throttle_safe(self, key: str, window_seconds: int) -> bool:
        now = time.time()
        last = _last_emitted.get(key)
        return last is not None and (now - last) < max(0, int(window_seconds))

    def mark_emitted_safe(self, key: str) -> None:
        _last_emitted[key] = time.time()
