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
from typing import Dict, Optional, List, Tuple, Any
import threading
from threading import RLock, Lock
from contextlib import contextmanager

from . import constants
from .config_manager import ConfigManager


_CANONICAL_AUDIO_KEYS = {
    "stop": constants.STOP,
    "subagentstop": constants.SUBAGENT_STOP,
    "notification": constants.NOTIFICATION,
    "agentstop": constants.SUBAGENT_STOP,  # legacy alias
    "usernotification": constants.NOTIFICATION,  # legacy alias
    "pretooluse": constants.PRE_TOOL_USE,
    "posttooluse": constants.POST_TOOL_USE,
    "sessionstart": constants.SESSION_START,
    "sessionend": constants.SESSION_END,
    "userpromptsubmit": constants.USER_PROMPT_SUBMIT,
}


def _canonical_audio_key(raw: str) -> str:
    if not isinstance(raw, str):
        return raw
    key = raw.replace("_", "").lower()
    return _CANONICAL_AUDIO_KEYS.get(key, raw)


def _load_config(config_manager: ConfigManager, config_filename: str = "audio_config.json") -> Dict:
    """Load audio configuration using ConfigManager."""
    try:
        return config_manager.get_config(config_filename)
    except Exception:
        return {}


def _which(cmd: str) -> Optional[str]:
    from shutil import which

    return which(cmd)


def _play_with(cmd: str, args: list[str], timeout_s: float = 5.0) -> int:
    try:
        # Goal 3: Asynchronous Audio Playbook - True fire-and-forget behavior
        # Start detached process for non-blocking audio playback
        p = subprocess.Popen(
            [cmd] + args, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent process group
        )
        # Don't wait for completion - immediately return success if process started
        # This ensures hooks execute in under 100ms as per Goal 3 requirements
        return 0  # Assume success for fire-and-forget playback
    except Exception:
        return 1


def _play_with_windows(filepath: str, volume: float = 1.0, timeout_s: float = 5.0) -> int:
    """Windows-specific audio player using winsound with volume control - Goal 3: Non-blocking"""
    try:
        import winsound

        if volume >= 1.0:
            # No volume adjustment needed, play original file asynchronously
            winsound.PlaySound(str(filepath), winsound.SND_FILENAME | winsound.SND_ASYNC)
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

        # Play adjusted audio from memory asynchronously
        wav_data = wav_buffer.getvalue()
        winsound.PlaySound(wav_data, winsound.SND_MEMORY | winsound.SND_ASYNC)
        return 0

    except Exception:
        # Fallback: play without volume control, still async
        try:
            import winsound
            winsound.PlaySound(str(filepath), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return 0
        except Exception:
            return 1


@dataclass
class AudioConfig:
    base_path: Path
    mappings: Dict[str, str]


class AudioManager:
    def __init__(self):
        # 線程安全鎖 - 添加在初始化最開始
        self._config_lock = RLock()      # 配置訪問鎖 (可重入)
        self._throttle_lock = Lock()     # 節流檔案操作鎖
        self._playback_lock = RLock()    # 音效播放協調鎖 (可重入)

        # 原有初始化程式碼用 config_lock 保護
        with self._config_lock:
            here_path = Path(__file__).resolve()
            # Project root is three levels up: utils -> hooks -> .claude -> <root>
            repo_root = here_path.parents[3]

            # Initialize ConfigManager with the utils directory
            config_dir = here_path.parent
            self._config_manager = ConfigManager.get_instance([str(config_dir)])

            # 1) ENV override (highest priority)
            env_dir = os.getenv("CLAUDE_SOUNDS_DIR") or os.getenv("AUDIO_SOUNDS_DIR")
            sounds_dir = Path(env_dir).expanduser() if env_dir else None
            if sounds_dir and not sounds_dir.is_absolute():
                sounds_dir = repo_root / sounds_dir

            # Load config early using ConfigManager
            cfg = _load_config(self._config_manager)

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
                constants.STOP: "task_complete.wav",
                constants.SUBAGENT_STOP: "agent_complete.wav",
                constants.NOTIFICATION: "user_prompt.wav",
                constants.PRE_TOOL_USE: "security_check.wav",
                constants.POST_TOOL_USE: "task_complete.wav",
                constants.SESSION_START: "session_start.wav",
                constants.SESSION_END: "session_complete.wav",
                constants.USER_PROMPT_SUBMIT: "user_prompt.wav",
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
        if name is None and audio_type == constants.SUBAGENT_STOP:
            name = self.config.mappings.get(constants.STOP)
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

    def play_audio_safe(self, audio_type: str, enabled: bool = False,
                       additional_context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[Path], Dict[str, Any]]:
        """線程安全的音效播放，支援並發請求處理."""

        # 使用播放鎖保護整個播放流程
        with self._playback_lock:
            # 線程安全的配置訪問
            with self._config_lock:
                audio_type = self._normalize_key(audio_type)
                path = self.resolve_file(audio_type)

            # 建立播放上下文 (線程安全)
            context = {
                "audioType": audio_type,
                "enabled": enabled,
                "playerCmd": self._player_cmd,
                "volume": self.volume,
                "filePath": str(path) if path else None,
                **(additional_context or {})
            }

            if not enabled or path is None:
                context["status"] = "skipped"
                context["reason"] = "disabled" if not enabled else "file_not_found"
                return False, path, context

            # 線程安全的播放執行
            return self._execute_playback_safe(path, context)

    def _execute_playback_safe(self, path: Path, context: Dict[str, Any]) -> tuple[bool, Path, Dict[str, Any]]:
        """執行音效播放，保證線程安全."""
        try:
            # 音效播放已經是異步和線程安全的
            if self._player_cmd == "winsound":
                rc = _play_with_windows(str(path), volume=self.volume, timeout_s=self._timeout_s)
            else:
                rc = _play_with(self._player_cmd, self._player_base_args + [str(path)], timeout_s=self._timeout_s)

            success = (rc == 0)
            context.update({
                "status": "played" if success else "failed",
                "returnCode": rc
            })
            return success, path, context

        except Exception as e:
            context.update({
                "status": "failed",
                "error": str(e)
            })
            return False, path, context

    def play_audio(self, audio_type: str, enabled: bool = False, additional_context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[Path], Dict[str, Any]]:
        """向後兼容的音效播放方法."""
        return self.play_audio_safe(audio_type, enabled, additional_context)

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

    def should_throttle_safe(self, key: str, window_seconds: int, now: Optional[float] = None) -> bool:
        """線程安全的節流檢查.

        Does not update the last-fired time. Call `mark_emitted_safe` after actually acting.
        """
        now = now or time.time()
        data = self._read_throttle_safe()
        last = float(data.get(key, 0))
        return (now - last) < float(window_seconds)

    def mark_emitted_safe(self, key: str, when: Optional[float] = None) -> None:
        """線程安全的發送標記."""
        when = when or time.time()
        data = self._read_throttle_safe()
        data[str(key)] = float(when)
        self._write_throttle_safe(data)

    def should_throttle(self, key: str, window_seconds: int, now: Optional[float] = None) -> bool:
        """向後兼容的節流檢查."""
        return self.should_throttle_safe(key, window_seconds, now)

    def mark_emitted(self, key: str, when: Optional[float] = None) -> None:
        """向後兼容的發送標記."""
        return self.mark_emitted_safe(key, when)

    # --- Threading Safety Methods -------------------------------------------
    
    def _use_file_locking(self) -> bool:
        """檢查是否可以使用檔案鎖定."""
        try:
            import fcntl  # Unix 系統
            return True
        except ImportError:
            try:
                import msvcrt  # Windows 系統
                return True
            except ImportError:
                return False

    def _read_with_file_lock(self, file_path: Path) -> Dict[str, float]:
        """使用檔案鎖定讀取數據."""
        import platform

        if platform.system() == "Windows":
            return self._read_windows_locked(file_path)
        else:
            return self._read_unix_locked(file_path)

    def _read_unix_locked(self, file_path: Path) -> Dict[str, float]:
        """Unix 系統檔案鎖定讀取."""
        import fcntl

        with open(file_path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # 共享鎖
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    # ensure float values
                    return {str(k): float(v) for k, v in data.items()}
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 解鎖
        return {}

    def _read_windows_locked(self, file_path: Path) -> Dict[str, float]:
        """Windows 系統檔案鎖定讀取."""
        import msvcrt

        with open(file_path, 'r') as f:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                data = json.load(f)
                if isinstance(data, dict):
                    # ensure float values
                    return {str(k): float(v) for k, v in data.items()}
            finally:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        return {}

    def _write_with_file_lock(self, file_path: Path, data: Dict[str, float]) -> None:
        """使用檔案鎖定寫入數據."""
        import platform

        if platform.system() == "Windows":
            self._write_windows_locked(file_path, data)
        else:
            self._write_unix_locked(file_path, data)

    def _write_unix_locked(self, file_path: Path, data: Dict[str, float]) -> None:
        """Unix 系統檔案鎖定寫入."""
        import fcntl

        with open(file_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 獨占鎖
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 解鎖

    def _write_windows_locked(self, file_path: Path, data: Dict[str, float]) -> None:
        """Windows 系統檔案鎖定寫入."""
        import msvcrt

        with open(file_path, 'w') as f:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                json.dump(data, f, indent=2)
            finally:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

    def _read_throttle_safe(self) -> Dict[str, float]:
        """線程安全的節流數據讀取，包含檔案鎖定."""
        with self._throttle_lock:
            try:
                if not self._throttle_path.exists():
                    return {}

                # 跨平台檔案鎖定實作
                if self._use_file_locking():
                    return self._read_with_file_lock(self._throttle_path)
                else:
                    # 降級到無鎖定模式
                    with open(self._throttle_path, 'r') as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            return {str(k): float(v) for k, v in data.items()}
                        return {}
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                return {}

    def _write_throttle_safe(self, data: Dict[str, float]) -> None:
        """線程安全的節流數據寫入，包含檔案鎖定."""
        with self._throttle_lock:
            try:
                self._throttle_path.parent.mkdir(parents=True, exist_ok=True)

                if self._use_file_locking():
                    self._write_with_file_lock(self._throttle_path, data)
                else:
                    # 降級到無鎖定模式
                    with open(self._throttle_path, 'w') as f:
                        json.dump(data, f, indent=2)
            except OSError:
                pass  # 靜默失敗，保持向後兼容性

    def get_config_safe(self, key: str, default: Any = None) -> Any:
        """線程安全的配置訪問."""
        with self._config_lock:
            return self._config_manager.get(key, default)

    def reload_config_safe(self) -> None:
        """線程安全的配置重載."""
        with self._config_lock:
            self._config_manager.clear_cache()

            # 重新載入配置
            cfg = _load_config(self._config_manager)

            # 更新映射和音量設定
            if "sound_files" in cfg:
                mappings = cfg["sound_files"].get("mappings", {})
                for raw_key, value in mappings.items():
                    canonical = _canonical_audio_key(raw_key)
                    self.config.mappings[canonical] = str(value)

            if "audio_settings" in cfg:
                volume = cfg["audio_settings"].get("volume")
                if isinstance(volume, (int, float)):
                    self.volume = max(0.0, min(1.0, float(volume)))

    @contextmanager
    def _performance_monitor(self, operation_name: str, warn_threshold_ms: float = 10.0):
        """監控操作性能，檢查線程鎖定開銷."""
        start = time.time()
        try:
            yield
        finally:
            duration = (time.time() - start) * 1000
            if duration > warn_threshold_ms:
                # 可選：記錄慢操作（用於調試）
                pass
