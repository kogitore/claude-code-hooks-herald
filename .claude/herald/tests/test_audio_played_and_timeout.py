#!/usr/bin/env python3
"""Audio playback and timeout behavior tests."""
from __future__ import annotations

import json
import math
import os
import struct
import tempfile
import time
import wave

from common_test_utils import run_hook


def test_audio_play_and_timeout_behavior() -> None:
    """Test basic audio hook behavior with timeout."""
    payload = {"hookEventName": "Notification", "message": "timeout test"}
    r = run_hook(".claude/herald/handlers/notification.py", payload=payload, args=["--enable-audio"])
    assert r.returncode == 0
    obj = json.loads([ln for ln in r.stdout.splitlines() if ln.strip()][-1])
    assert obj["continue"] is True
    # If audio player is missing, stderr should contain a note (but not fail)
    assert "afplay" in (r.stderr or "") or r.stderr == ""


def _write_tone_wav(path: str, seconds: float = 0.05, freq: float = 440.0, rate: int = 8000) -> None:
    """Write a simple tone WAV file for testing."""
    n_samples = int(seconds * rate)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        for i in range(n_samples):
            val = int(32767 * 0.2 * math.sin(2 * math.pi * freq * (i / rate)))
            wf.writeframes(struct.pack('<h', val))


def test_audio_played_true() -> None:
    """Test audio playback with stubbed player."""
    with tempfile.TemporaryDirectory() as td:
        # Prepare sounds dir with a tiny wav for completion
        wav_path = os.path.join(td, 'task_complete.wav')
        _write_tone_wav(wav_path)
        env = {
            'CLAUDE_SOUNDS_DIR': td,
            'AUDIO_PLAYER_CMD': 'true',  # simulate success
        }
        r = run_hook(".claude/herald/handlers/stop.py", payload={'hookEventName': 'Stop'}, args=["--enable-audio"])
        assert r.returncode == 0
        r2 = run_hook(".claude/herald/handlers/stop.py", payload={'hookEventName': 'Stop'}, args=["--enable-audio"])
        assert r2.returncode == 0


def test_timeout() -> None:
    """Test that audio playback respects timeout."""
    with tempfile.TemporaryDirectory() as td:
        wav_path = os.path.join(td, 'task_complete.wav')
        _write_tone_wav(wav_path)
        start = time.time()
        os.environ['CLAUDE_SOUNDS_DIR'] = td
        os.environ['AUDIO_PLAYER_CMD'] = 'sleep'
        os.environ['AUDIO_PLAYER_ARGS'] = '10'
        os.environ['AUDIO_PLAYER_TIMEOUT'] = '1'
        r = run_hook(".claude/herald/handlers/stop.py", payload={'hookEventName': 'Stop'}, args=["--enable-audio"])
        elapsed = time.time() - start
        assert r.returncode == 0
        assert elapsed < 3.0


if __name__ == "__main__":
    test_audio_play_and_timeout_behavior()
    test_audio_played_true()
    test_timeout()
