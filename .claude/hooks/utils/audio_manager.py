#!/usr/bin/env python3
"""
Minimal Audio Manager for Claude Code Hooks (pure local audio files)

- No TTS/LLM, no network calls
- Uses system audio players when available (afplay/ffplay/aplay/winsound)
- Cross-platform volume control: macOS/Linux via player args, Windows via audioop
- Paths simplified: repo root is assumed at Path(__file__).parents[3]
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
import time
from pathlib import Path
from typing import Dict, Optional, List, Tuple


_CANONICAL_AUDIO_KEYS = {
    "stop": "Stop",
    "subagentstop": "SubagentStop",
    "notification": "Notification",
    "agentstop": "SubagentStop",  # legacy alias
    "usernotification": "Notification",  # legacy alias
    "pretooluse": "PreToolUse",
    "posttooluse": "PostToolUse",
    "sessionstart": "SessionStart",
    "sessionend": "SessionEnd",
    "userpromptsubmit": "UserPromptSubmit",
}


def _canonical_audio_key(raw: str) -> str:
    if not isinstance(raw, str):
        return raw
    key = raw.replace("_", "").lower()
    return _CANONICAL_AUDIO_KEYS.get(key, raw)


def _load_config(config_path: Path) -> Dict:
    try:
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _which(cmd: str) -> Optional[str]:
    from shutil import which

    return which(cmd)


def _play_with(cmd: str, args: list[str], timeout_s: float = 5.0) -> int:
    try:
        # For audio players, we want fire-and-forget behavior
        # Use Popen with detached process to avoid waiting for audio completion
        p = subprocess.Popen([cmd] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Quick check if process started successfully
        if p.poll() is None:  # Process is still running (good)
            return 0
        else:  # Process exited immediately (likely error)
            return p.returncode
    except Exception:
        return 1


def _play_with_windows(filepath: str, volume: float = 1.0, timeout_s: float = 5.0) -> int:
    """Windows-specific audio player using winsound with volume control"""
    try:
        import winsound

        if volume >= 1.0:
            # No volume adjustment needed, play original file
            winsound.PlaySound(str(filepath), winsound.SND_FILENAME)
            return 0

        # Perform volume adjustment using standard library
        import audioop
        import wave
        import io

        # Read WAV file
        with wave.open(str(filepath), 'rb') as wav_file:
            frames = wav_file.readframes(-1)
            sample_width = wav_file.getsampwidth()
            channels = wav_file.getnchannels()
            framerate = wav_file.getframerate()

        # Adjust volume (volume range 0.0-1.0)
        adjusted_frames = audioop.mul(frames, sample_width, volume)

        # Create in-memory WAV data
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as out_wav:
            out_wav.setnchannels(channels)
            out_wav.setsampwidth(sample_width)
            out_wav.setframerate(framerate)
            out_wav.writeframes(adjusted_frames)

        # Play adjusted audio from memory
        wav_data = wav_buffer.getvalue()
        winsound.PlaySound(wav_data, winsound.SND_MEMORY)
        return 0

    except Exception:
        # Fallback: play without volume control
        try:
            import winsound
            winsound.PlaySound(str(filepath), winsound.SND_FILENAME)
            return 0
        except Exception:
            return 1


@dataclass
class AudioConfig:
    base_path: Path
    mappings: Dict[str, str]


class AudioManager:
    def __init__(self):
        here_path = Path(__file__).resolve()
        # Project root is three levels up: utils -> hooks -> .claude -> <root>
        repo_root = here_path.parents[3]

        # 1) ENV override (highest priority)
        env_dir = os.getenv("CLAUDE_SOUNDS_DIR") or os.getenv("AUDIO_SOUNDS_DIR")
        sounds_dir = Path(env_dir).expanduser() if env_dir else None
        if sounds_dir and not sounds_dir.is_absolute():
            sounds_dir = repo_root / sounds_dir

        # Load config early
        cfg = _load_config(here_path.parent / "audio_config.json")

        # 2) Config base_path if ENV not set
        if not sounds_dir:
            try:
                base = cfg.get("sound_files", {}).get("base_path")
                if isinstance(base, str):
                    base_path = Path(base)
                    sounds_dir = base_path if base_path.is_absolute() else (repo_root / base_path)
            except Exception:
                sounds_dir = None

        # 3) Default path relative to repo root
        if not sounds_dir:
            sounds_dir = repo_root / ".claude" / "sounds"

        # Defaults map to official event names
        mappings = {
            "Stop": "task_complete.wav",
            "SubagentStop": "agent_complete.wav",
            "Notification": "user_prompt.wav",
            "PreToolUse": "security_check.wav",
            "PostToolUse": "task_complete.wav",
            "SessionStart": "session_start.wav",
            "SessionEnd": "session_complete.wav",
            "UserPromptSubmit": "user_prompt.wav",
        }

        # Optional config override (config wins over defaults)
        volume = 0.2
        throttle_cfg: Dict[str, int] = {}

        try:
            m = cfg.get("sound_files", {}).get("mappings", {})
            if isinstance(m, dict):
                for raw_key, value in m.items():
                    canonical = _canonical_audio_key(raw_key)
                    mappings[canonical] = str(value)
            vol = cfg.get("audio_settings", {}).get("volume")
            if isinstance(vol, (int, float)):
                volume = max(0.0, min(1.0, float(vol)))
            throttle_settings = cfg.get("audio_settings", {}).get("throttle_seconds", {})
            if isinstance(throttle_settings, dict):
                for raw_key, value in throttle_settings.items():
                    if isinstance(value, (int, float)):
                        canonical = _canonical_audio_key(str(raw_key))
                        throttle_cfg[canonical] = max(0, int(value))
        except Exception:
            pass

        self.config = AudioConfig(base_path=sounds_dir, mappings=mappings)
        self.volume = volume
        self._throttle_cfg = throttle_cfg

        # Throttle store under repo_root/logs
        self._throttle_path = repo_root / "logs" / "audio_throttle.json"
        try:
            self._throttle_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        # Player selection & timeout
        self._timeout_s = float(os.getenv("AUDIO_PLAYER_TIMEOUT", "5"))
        self._player_cmd, self._player_base_args = self._select_player()

    def _select_player(self) -> Tuple[Optional[str], List[str]]:
        # ENV override first
        cmd = os.getenv("AUDIO_PLAYER_CMD")
        base_args = os.getenv("AUDIO_PLAYER_ARGS", "").split() if os.getenv("AUDIO_PLAYER_ARGS") else []
        if cmd:
            return cmd, base_args
        # Auto-detect
        if _which("afplay"):
            args: List[str] = ["-v", f"{self.volume:.3f}"]
            return "afplay", args
        if _which("ffplay"):
            args = ["-nodisp", "-autoexit", "-loglevel", "error", "-volume", str(int(round(self.volume * 100)))]
            return "ffplay", args
        if _which("aplay"):
            return "aplay", []  # aplay doesn't support volume uniformly
        # Windows fallback: use winsound via Python
        import platform
        if platform.system() == "Windows":
            return "winsound", []  # Special marker for Windows native audio
        return None, []

    def _normalize_key(self, audio_type: str) -> str:
        return _canonical_audio_key(audio_type)

    def resolve_file(self, audio_type: str) -> Optional[Path]:
        audio_type = self._normalize_key(audio_type)
        name = self.config.mappings.get(audio_type)
        if name is None and audio_type == "SubagentStop":
            name = self.config.mappings.get("Stop")
        if not name:
            return None
        p = self.config.base_path / str(name)
        return p if p.exists() else None

    def get_throttle_window(self, audio_type: str, default_seconds: int) -> int:
        """Return throttle window for audio_type using config overrides."""
        audio_type = self._normalize_key(audio_type)
        cfg_value = self._throttle_cfg.get(audio_type)
        if isinstance(cfg_value, int) and cfg_value >= 0:
            return cfg_value
        return max(0, int(default_seconds))

    def play_audio(self, audio_type: str, enabled: bool = False) -> tuple[bool, Optional[Path]]:
        """Attempt to play local audio. Returns (played, path).

        - If not enabled or file missing, returns (False, maybe_path)
        - Does not raise on failure
        """
        audio_type = self._normalize_key(audio_type)
        path = self.resolve_file(audio_type)
        if not enabled or path is None:
            return False, path

        # Use cached player
        if self._player_cmd:
            if self._player_cmd == "winsound":
                rc = _play_with_windows(str(path), volume=self.volume, timeout_s=self._timeout_s)
            else:
                rc = _play_with(self._player_cmd, self._player_base_args + [str(path)], timeout_s=self._timeout_s)
            return (rc == 0), path
        return False, path

    # --- Throttling helpers -------------------------------------------------
    def _read_throttle(self) -> Dict[str, float]:
        try:
            if self._throttle_path.exists():
                txt = self._throttle_path.read_text(encoding="utf-8")
                data = json.loads(txt)
                if isinstance(data, dict):
                    # ensure float values
                    return {str(k): float(v) for k, v in data.items()}
        except Exception:
            # Corrupted file: reset empty
            try:
                self._throttle_path.write_text("{}", encoding="utf-8")
            except Exception:
                pass
        return {}

    def _write_throttle(self, data: Dict[str, float]) -> None:
        try:
            # Best-effort advisory lock (POSIX); ignore on platforms lacking fcntl
            try:
                import fcntl  # type: ignore
            except Exception:
                fcntl = None
            tmp = self._throttle_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                if fcntl:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    except Exception:
                        pass
                f.write(json.dumps(data))
                try:
                    if fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            os.replace(tmp, self._throttle_path)
        except Exception:
            pass

    def should_throttle(self, key: str, window_seconds: int, now: Optional[float] = None) -> bool:
        """Return True if an event with `key` should be throttled.

        Does not update the last-fired time. Call `mark_emitted` after actually acting.
        """
        now = now or time.time()
        data = self._read_throttle()
        last = float(data.get(key, 0))
        return (now - last) < float(window_seconds)

    def mark_emitted(self, key: str, when: Optional[float] = None) -> None:
        when = when or time.time()
        data = self._read_throttle()
        data[str(key)] = float(when)
        self._write_throttle(data)
