# Removed per TESTS_CLEANUP_GUIDE Phase 1
#!/usr/bin/env python3
from __future__ import annotations
import json
import time
from common_test_utils import run_hook

def test_audio_play_and_timeout_behavior() -> None:
    payload = {"hookEventName": "Notification", "message": "timeout test"}
    r = run_hook(".claude/hooks/notification.py", payload=payload, args=["--enable-audio"])
    assert r.returncode == 0
    obj = json.loads([ln for ln in r.stdout.splitlines() if ln.strip()][-1])
    assert obj["continue"] is True
    # If audio player is missing, stderr should contain a note (but not fail)
    assert "afplay" in (r.stderr or "") or r.stderr == ""
#!/usr/bin/env python3
from __future__ import annotations

import os
import wave
import struct
import tempfile
import time

from common_test_utils import run_hook


def _write_tone_wav(path: str, seconds: float = 0.05, freq: float = 440.0, rate: int = 8000):
    n_samples = int(seconds * rate)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        for i in range(n_samples):
            val = int(32767 * 0.2 * __import__('math').sin(2 * __import__('math').pi * freq * (i / rate)))
            wf.writeframes(struct.pack('<h', val))


def test_audio_played_true() -> None:
    with tempfile.TemporaryDirectory() as td:
        # Prepare sounds dir with a tiny wav for completion
        wav_path = os.path.join(td, 'task_complete.wav')
        _write_tone_wav(wav_path)
        env = {
            'CLAUDE_SOUNDS_DIR': td,
            'AUDIO_PLAYER_CMD': 'true',  # simulate success
        }
        r = run_hook(".claude/hooks/stop.py", payload={'hookEventName': 'Stop'}, args=["--enable-audio"], timeout=3.0, env_overrides=env)
        assert r.returncode == 0
        r2 = run_hook(".claude/hooks/stop.py", payload={'hookEventName': 'Stop'}, args=["--enable-audio"], timeout=3.0, env_overrides=env)
        assert r2.returncode == 0


def test_timeout() -> None:
    with tempfile.TemporaryDirectory() as td:
        wav_path = os.path.join(td, 'task_complete.wav')
        _write_tone_wav(wav_path)
        start = time.time()
        os.environ['CLAUDE_SOUNDS_DIR'] = td
        os.environ['AUDIO_PLAYER_CMD'] = 'sleep'
        os.environ['AUDIO_PLAYER_ARGS'] = '10'
        os.environ['AUDIO_PLAYER_TIMEOUT'] = '1'
        r = run_hook(".claude/hooks/stop.py", payload={'hookEventName': 'Stop'}, args=["--enable-audio"], timeout=5.0)
        elapsed = time.time() - start
        assert r.returncode == 0
        assert elapsed < 3.0


def main():
    test_audio_played_true()
    test_timeout()
