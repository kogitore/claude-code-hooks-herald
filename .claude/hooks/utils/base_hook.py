#!/usr/bin/env python3
"""
Temporary simplified BaseHook - compatibility shim during Phase 1 cleanup.
Goal: keep existing hooks running while audio/middleware layers are removed.
Important: this BaseHook does NOT play audio; dispatcher is responsible.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import json
from pathlib import Path


@dataclass
class HookExecutionResult:
    """Simple result class for hook execution"""
    # Execution payload for JSON response (hooks often clear this)
    payload: Dict[str, Any] = field(default_factory=dict)
    # Notes/errors for debug logging
    notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

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
    
    def execute(self, payload: Dict[str, Any], enable_audio: bool = True, **kwargs: Any) -> HookExecutionResult:
        """Execute the hook logic and return meta for dispatcher-driven audio.

        Compatibility behaviour:
        - If subclass implements handle_hook_logic, use it to build HookExecutionResult
        - Otherwise, call process() and return empty payload
        - Do NOT actually play audio; only attach audio metadata
        """
        payload = payload or {}

        result: HookExecutionResult
        if hasattr(self, "handle_hook_logic"):
            try:
                # parsed_args is commonly used; pass through when available
                parsed_args = kwargs.get("parsed_args")
                result = getattr(self, "handle_hook_logic")(payload, parsed_args=parsed_args)
                if not isinstance(result, HookExecutionResult):
                    # Fallback to empty result if subclass returned wrong type
                    result = HookExecutionResult(payload={})
            except Exception as exc:  # delegate to subclass error handler if present
                if hasattr(self, "handle_error"):
                    processed = getattr(self, "handle_error")(exc)
                    result = HookExecutionResult(payload=processed or {})
                else:
                    result = HookExecutionResult(payload={})
        else:
            processed = self.process(payload)
            result = HookExecutionResult(payload=dict(processed) if isinstance(processed, dict) else {})

        # Attach audio metadata for dispatcher (no playback here)
        self._attach_audio(
            result,
            self.default_audio_event,
            enable_audio=bool(enable_audio),
            throttle_key=self._default_throttle_key(self.default_audio_event or "default", result) if self.default_throttle_seconds else None,
            throttle_seconds=int(self.default_throttle_seconds) if self.default_throttle_seconds else None,
        )
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

    # Attach audio metadata only; dispatcher will actually play audio
    def _attach_audio(
        self,
        result: HookExecutionResult,
        audio_event: Optional[str],
        *,
        enable_audio: bool,
        throttle_key: Optional[str],
        throttle_seconds: Optional[int],
    ) -> None:
        if not audio_event:
            return
        result.audio_type = audio_event
        if throttle_seconds and throttle_seconds > 0:
            result.throttle_window = int(throttle_seconds)
        if throttle_key:
            result.throttle_key = throttle_key

    # Minimal compatibility output helper used by some hook CLIs
    def emit_json(self, result: HookExecutionResult) -> None:
        try:
            print(json.dumps({"continue": bool(getattr(result, "continue_value", True))}))
        except Exception:
            print('{"continue": true}')