#!/usr/bin/env python3
"""Base hook framework for Claude Code audio hooks.

This module provides the BaseHook abstraction referenced in Phase 1 of the
roadmap. It centralises the common control flow for validating inputs,
executing hook logic, graceful error handling, and optional audio playback via
`AudioManager`. Concrete hooks should inherit from `BaseHook` and implement the
abstract methods defined here while keeping their own modules thin.
"""
from __future__ import annotations

import abc
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .audio_manager import AudioManager
from .common_io import generate_audio_notes


@dataclass
class HookExecutionResult:
    """Encapsulates the outcome of a hook execution cycle."""

    continue_value: bool = True
    payload: Dict[str, Any] = field(default_factory=dict)
    audio_type: Optional[str] = None
    throttle_key: Optional[str] = None
    throttle_window: Optional[int] = None
    audio_played: bool = False
    audio_path: Optional[Path] = None
    throttled: bool = False
    notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def build_response(self) -> Dict[str, Any]:
        response = {"continue": self.continue_value}
        response.update(self.payload)
        return response


class BaseHook(abc.ABC):
    """Abstract base class for Claude Code audio hooks."""

    default_audio_event: Optional[str] = None
    default_throttle_seconds: int = 0

    def __init__(self, *, audio_manager: Optional[AudioManager] = None) -> None:
        self.audio_manager = audio_manager or AudioManager()

    # -- Contract methods -------------------------------------------------
    @abc.abstractmethod
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Return True when the hook input is structurally valid."""

    @abc.abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hook's core logic and return additional payload fields."""

    @abc.abstractmethod
    def handle_error(self, error: Exception) -> Dict[str, Any]:
        """Transform an exception into payload fields for graceful fallback."""

    # -- Public API -------------------------------------------------------
    def execute(
        self,
        data: Optional[Dict[str, Any]],
        *,
        enable_audio: bool = False,
        audio_event: Optional[str] = None,
        throttle_key: Optional[str] = None,
        throttle_seconds: Optional[int] = None,
    ) -> HookExecutionResult:
        payload = data or {}
        result = HookExecutionResult()
        try:
            valid = self.validate_input(payload)
        except Exception as exc:  # pragma: no cover - defensive path
            return self._error_result(exc, result)

        if not valid:
            result.errors.append("input_validation_failed")
            return result

        try:
            extra = self.process(payload)
            if extra:
                result.payload.update(extra)
        except Exception as exc:
            result = self._error_result(exc, result)
        else:
            event = audio_event or self.default_audio_event
            if event:
                self._attach_audio(
                    result,
                    event,
                    enable_audio=enable_audio,
                    throttle_key=throttle_key,
                    throttle_seconds=throttle_seconds,
                )
        return result

    def emit_json(self, result: HookExecutionResult) -> None:
        """Print the JSON response and telemetry to `stderr` if present."""
        try:
            print(json.dumps(result.build_response()))
        except Exception:  # pragma: no cover - final safety net
            print(json.dumps({"continue": True}))

        if result.notes or result.errors:
            segments = ["[Hook]"]
            if result.notes:
                segments.append(f"notes={'|'.join(result.notes)}")
            if result.errors:
                segments.append(f"errors={'|'.join(result.errors)}")
            try:
                print(" ".join(segments), file=sys.stderr)
            except Exception:  # pragma: no cover - diagnostic best effort
                pass

    # -- Internal helpers -------------------------------------------------
    def _error_result(self, error: Exception, result: HookExecutionResult) -> HookExecutionResult:
        result.errors.append(type(error).__name__)
        try:
            recovery = self.handle_error(error) or {}
            if recovery:
                result.payload.update(recovery)
        except Exception:  # pragma: no cover - avoid cascading failures
            pass
        return result

    def _attach_audio(
        self,
        result: HookExecutionResult,
        audio_event: str,
        *,
        enable_audio: bool,
        throttle_key: Optional[str],
        throttle_seconds: Optional[int],
    ) -> None:
        window_default = throttle_seconds
        if window_default is None:
            window_default = self.default_throttle_seconds
        window_default = int(window_default or 0)

        window = self.audio_manager.get_throttle_window(audio_event, window_default)

        throttle_key = throttle_key or self._default_throttle_key(audio_event, result)

        played, path, throttled = self._play_audio(
            audio_event,
            enable_audio=enable_audio,
            throttle_key=throttle_key,
            throttle_seconds=window,
        )

        result.audio_type = audio_event
        result.throttle_key = throttle_key
        result.throttle_window = window
        result.audio_played = played
        result.audio_path = path
        result.throttled = throttled
        result.notes.extend(
            generate_audio_notes(
                throttled=throttled,
                path=path,
                played=played,
                enabled=enable_audio,
                throttle_msg=f"Throttled (<= {window}s)",
            )
        )

    def _play_audio(
        self,
        audio_event: str,
        *,
        enable_audio: bool,
        throttle_key: Optional[str],
        throttle_seconds: int,
    ) -> Tuple[bool, Optional[Path], bool]:
        throttled = False
        path = self.audio_manager.resolve_file(audio_event)
        played = False
        if throttle_seconds > 0 and throttle_key:
            throttled = self.audio_manager.should_throttle(throttle_key, throttle_seconds)
        if not throttled and enable_audio:
            played, path = self.audio_manager.play_audio(audio_event, enabled=True)
            if throttle_key:
                self.audio_manager.mark_emitted(throttle_key)
        return played, path, throttled

    def _default_throttle_key(self, audio_event: str, result: HookExecutionResult) -> str:
        marker = None
        if isinstance(result.payload, dict):
            marker = result.payload.get("marker")
            if not marker and audio_event.lower() == "notification":
                message = result.payload.get("message")
                if isinstance(message, str) and message.strip():
                    digest = hashlib.sha1(message.encode("utf-8")).hexdigest()[:12]
                    return f"Notification:{digest}"
        marker = marker or "default"
        return f"{audio_event}:{marker}"
