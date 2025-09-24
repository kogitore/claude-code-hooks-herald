#!/usr/bin/env python3
"""
Temporary simplified BaseHook - compatibility shim during Phase 1 cleanup.
Goal: keep existing hooks running while audio/middleware layers are removed.
Important: this BaseHook does NOT play audio; dispatcher is responsible.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import json
from pathlib import Path


@dataclass
class HookExecutionResult:
    """Simple result class for hook execution"""
    # Execution payload for JSON response (hooks often clear this)
    payload: Dict[str, Any] = None  # type: ignore[assignment]
    # Notes/errors for debug logging
    notes: List[str] = None  # type: ignore[assignment]
    errors: List[str] = None  # type: ignore[assignment]

    # Audio-related fields (dispatcher will fill these later)
    audio_played: bool = False
    throttled: bool = False
    audio_type: Optional[str] = None
    throttle_key: Optional[str] = None
    throttle_window: Optional[int] = None
    audio_path: Optional[Path] = None

    # Decision-related fields (security hooks)
    blocked: bool = False
    decision_payload: Optional[Dict[str, Any]] = None
    # Continue flag for dispatcher mapping
    continue_value: bool = True


class BaseHook:
    """
    Temporary base class for hooks - WILL BE DELETED in Phase 3
    This exists only to keep existing hooks working during refactoring
    """
    
    def __init__(self, audio_manager=None):
        self.audio_manager = audio_manager
        self.default_audio_event = None
        self.default_throttle_seconds = 0
    
    def execute(self, payload: Dict[str, Any], enable_audio: bool = True, **_: Any) -> HookExecutionResult:
        """Execute the hook logic and return meta for dispatcher-driven audio."""
        # Process hook-specific logic (usually returns {})
        payload = payload or {}
        processed = self.process(payload)

        # Prepare result; do NOT play audio here (dispatcher owns playback)
        result = HookExecutionResult(
            payload=dict(processed) if isinstance(processed, dict) else {},
            notes=[],
            errors=[],
        )
        # Provide defaults used by dispatcher
        result.audio_type = self.default_audio_event
        if self.default_throttle_seconds > 0:
            result.throttle_window = int(self.default_throttle_seconds)
            result.throttle_key = self._default_throttle_key(result.audio_type or "default", result)
        return result
    
    def process(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Override this method in subclasses
        Most hooks return {} - which shows they are useless
        """
        return {}

    # Compatibility: allow hooks to customize throttle key
    def _default_throttle_key(self, audio_event: str, result: HookExecutionResult) -> str:  # noqa: ARG002
        return f"{audio_event}:default"

    # Minimal compatibility output helper used by some hook CLIs
    def emit_json(self, result: HookExecutionResult) -> None:
        try:
            print(json.dumps({"continue": bool(getattr(result, "continue_value", True))}))
        except Exception:
            print('{"continue": true}')