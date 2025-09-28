#!/usr/bin/env python3
"""Linus-style simplified Audio Manager for Claude Code Hooks.

KISS principle: Simple, working, maintainable.
No over-engineering. No ceremony. Just works.

Functionality:
- Load audio config from audio_config.json
- Map events to audio files
- Play audio with system player (afplay/ffplay/aplay)
- Basic throttling to prevent spam
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Tuple, Any

from . import constants


@dataclass
class AudioConfig:
    """Simple audio configuration."""
    base_path: Path
    mappings: Dict[str, str]


def _which(cmd: str) -> bool:
    """Check if command exists in PATH."""
    import shutil
    return shutil.which(cmd) is not None


def _load_config(repo_root: Path) -> Tuple[AudioConfig, float, Dict[str, int]]:
    """Load audio configuration. Simple and direct."""
    config_path = repo_root / ".claude" / "hooks" / "utils" / "audio_config.json"

    # Defaults
    base_path = repo_root / ".claude" / "sounds"
    mappings = {}
    volume = 0.2
    throttle = {}

    try:
        if config_path.exists():
            data = json.loads(config_path.read_text())

            # Extract mappings
            if "sound_files" in data:
                sf = data["sound_files"]
                if "mappings" in sf:
                    mappings = sf["mappings"]

            # Extract settings
            if "audio_settings" in data:
                settings = data["audio_settings"]
                volume = float(settings.get("volume", 0.2))
                if "throttle_seconds" in settings:
                    throttle = {k: int(v) for k, v in settings["throttle_seconds"].items()}

    except Exception:
        pass  # Use defaults on any error

    return AudioConfig(base_path, mappings), volume, throttle


class AudioManager:
    """Simplified audio manager. No over-engineering."""

    def __init__(self):
        # Find repo root (3 levels up from utils/)
        self.repo_root = Path(__file__).resolve().parents[3]

        # Load config
        self.config, self.volume, self._throttle_cfg = _load_config(self.repo_root)

        # Throttle tracking
        self._throttle_data: Dict[str, float] = {}
        self._throttle_lock = Lock()

        # Select audio player
        self._player_cmd, self._player_args = self._select_player()

    def _select_player(self) -> Tuple[Optional[str], list[str]]:
        """Select best available audio player."""
        # ENV override
        cmd = os.getenv("AUDIO_PLAYER_CMD")
        if cmd:
            args = os.getenv("AUDIO_PLAYER_ARGS", "").split()
            return cmd, args

        # Auto-detect by platform
        import platform
        system = platform.system().lower()

        if system == "windows":
            # Windows: Try winsound first (built-in), then PowerShell
            try:
                import winsound
                return "winsound", []  # Special marker for winsound
            except ImportError:
                pass
            if _which("powershell"):
                return "powershell", ["-Command", f"(New-Object System.Media.SoundPlayer '{{0}}').PlaySync()"]
            # Fallback: No audio player (silent mode)
            return None, []
        elif system == "darwin":  # macOS
            if _which("afplay"):
                return "afplay", ["-v", f"{self.volume:.3f}"]
        else:  # Linux and others
            if _which("ffplay"):
                return "ffplay", ["-nodisp", "-autoexit", "-loglevel", "error",
                                "-volume", str(int(self.volume * 100))]
            if _which("aplay"):
                return "aplay", []

        return None, []  # No player available

    def resolve_file(self, audio_type: str) -> Optional[Path]:
        """Resolve audio type to file path."""
        # Normalize event name
        audio_type = audio_type.strip()

        # Get mapped filename
        filename = self.config.mappings.get(audio_type)
        if not filename:
            return None

        # Check if file exists
        path = self.config.base_path / filename
        return path if path.exists() else None

    def should_throttle_safe(self, key: str, window_seconds: int) -> bool:
        """Thread-safe throttle check."""
        with self._throttle_lock:
            now = time.time()
            last = self._throttle_data.get(key, 0)
            return (now - last) < window_seconds

    def mark_emitted_safe(self, key: str) -> None:
        """Thread-safe throttle marking."""
        with self._throttle_lock:
            self._throttle_data[key] = time.time()

    def play_audio_safe(self, audio_type: str, enabled: bool = True,
                       additional_context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[Path], Dict[str, Any]]:
        """Play audio. Simple and reliable."""
        context = {
            "audioType": audio_type,
            "enabled": enabled,
            "playerCmd": self._player_cmd,
            "volume": self.volume,
            **(additional_context or {})
        }

        # Check if enabled
        if not enabled:
            context.update({"status": "skipped", "reason": "disabled"})
            return False, None, context

        # Check if player available
        if not self._player_cmd:
            context.update({"status": "skipped", "reason": "no_player"})
            return False, None, context

        # Resolve file path
        path = self.resolve_file(audio_type)
        context["filePath"] = str(path) if path else None

        if not path:
            context.update({"status": "skipped", "reason": "file_not_found"})
            return False, path, context

        # Play audio
        try:
            import platform
            system = platform.system().lower()

            if system == "windows" and self._player_cmd == "winsound":
                # Windows winsound: Direct Python API (most reliable)
                try:
                    import winsound
                    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                    context.update({"status": "played", "method": "winsound"})
                    return True, path, context
                except Exception as e:
                    context.update({"status": "failed", "error": f"winsound: {e}"})
                    return False, path, context

            elif system == "windows" and self._player_cmd == "powershell":
                # Windows PowerShell: Format path correctly and use shorter timeout
                cmd = [self._player_cmd] + [arg.format(str(path)) for arg in self._player_args]
                result = subprocess.run(cmd, capture_output=True, timeout=2,
                                      creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            else:
                # Unix systems: Standard approach
                cmd = [self._player_cmd] + self._player_args + [str(path)]
                result = subprocess.run(cmd, capture_output=True, timeout=3)

            success = result.returncode == 0

            context.update({
                "status": "played" if success else "failed",
                "returnCode": result.returncode
            })
            return success, path, context

        except subprocess.TimeoutExpired:
            context.update({"status": "failed", "error": "timeout"})
            return False, path, context
        except Exception as e:
            context.update({"status": "failed", "error": str(e)})
            return False, path, context

    # Legacy compatibility methods
    def play_audio(self, audio_type: str, enabled: bool = False,
                  additional_context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[Path], Dict[str, Any]]:
        """Backward compatible audio play method."""
        return self.play_audio_safe(audio_type, enabled, additional_context)

    def should_throttle(self, key: str, window_seconds: int) -> bool:
        """Backward compatible throttle check."""
        return self.should_throttle_safe(key, window_seconds)