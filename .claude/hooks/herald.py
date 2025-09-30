#!/usr/bin/env python3
"""Simplified herald dispatcher (Linus-style optimization).

Maps hook event -> handler function. Provides:
 - stdin JSON parse (best effort)
 - audio via existing HandlerResult fields
 - standard JSON response contract

No middleware. No registry. No ceremony.
KISS principle: Simple, working, maintainable.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Callable

from utils import constants
from utils.audio_manager import AudioManager as _AM
from utils.handler_result import HandlerResult

# Type aliases for clarity
JsonDict = dict[str, object]  # JSON-serializable dict (str, int, bool, dict, list, None)
HookResponse = dict[str, object]  # Hook response with continue, hookSpecificOutput, etc.


# Dynamic import handlers to completely avoid circular dependency
def _lazy_import_handlers() -> dict[str, Callable[[object], HandlerResult]]:
    """Dynamically import handlers to break circular dependency.

    Uses importlib to load modules at runtime, avoiding top-level imports
    that would create circular dependencies.
    """
    handler_map: dict[str, tuple[str, str]] = {
        constants.NOTIFICATION: ('notification', 'handle_notification'),
        constants.STOP: ('stop', 'handle_stop'),
        constants.SUBAGENT_STOP: ('stop', 'handle_subagent_stop'),
        constants.PRE_TOOL_USE: ('pre_tool_use', 'handle_pre_tool_use'),
        constants.POST_TOOL_USE: ('post_tool_use', 'handle_post_tool_use'),
        constants.SESSION_START: ('session_start', 'handle_session_start'),
        constants.SESSION_END: ('session_end', 'handle_session_end'),
        constants.USER_PROMPT_SUBMIT: ('user_prompt_submit', 'handle_user_prompt_submit'),
    }

    handlers: dict[str, Callable[[object], HandlerResult]] = {}
    for event_type, (module_name, func_name) in handler_map.items():
        module = importlib.import_module(module_name)
        handlers[event_type] = getattr(module, func_name)

    return handlers


# Initialize HANDLERS lazily to avoid circular import
_handlers_cache: dict[str, Callable[[object], HandlerResult]] | None = None

def _get_handlers() -> dict[str, Callable[[object], HandlerResult]]:
    """Get handlers dict, initializing lazily on first access."""
    global _handlers_cache
    if _handlers_cache is None:
        _handlers_cache = _lazy_import_handlers()
    return _handlers_cache

# Module-level __getattr__ for lazy HANDLERS loading (PEP 562)
def __getattr__(name: str) -> object:
    """Lazy load HANDLERS on first access for backward compatibility."""
    if name == "HANDLERS":
        return _get_handlers()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def _read_stdin() -> JsonDict:
    """Read and parse JSON from stdin.

    Returns a dict that represents JSON-serializable data from stdin.
    On parse error, returns empty dict.
    """
    try:
        raw = sys.stdin.read().strip() or "{}"
        data = json.loads(raw)  # Returns Any by design (JSON can be anything)
        if isinstance(data, dict):
            return data  # type: ignore[return-value]  # JsonDict is dict[str, object]
        return {}
    except Exception:
        return {}


def _play_audio(audio_type: object, throttle_key: object, throttle_window: object) -> None:
    """Play audio with optional throttling (AudioManager handles platform quirks).

    AudioManager.play_audio_safe() already has timeout protection on all platforms,
    so we don't need separate Windows threading logic here.
    """
    if not audio_type:
        return
    try:
        am = _AM()
        # Convert to proper types for AudioManager calls
        audio_str = str(audio_type) if audio_type else ""
        key_str = str(throttle_key) if throttle_key else ""
        window_int = int(throttle_window) if isinstance(throttle_window, (int, float)) else 0

        # Check throttle before playing
        if key_str and window_int > 0:
            try:
                if am.should_throttle_safe(key_str, window_int):
                    return
            except Exception:
                pass
        # Play audio (AudioManager handles timeout internally)
        played, _path, _ctx = am.play_audio_safe(audio_str, enabled=True)
        # Mark as emitted if successful
        if played and key_str and window_int > 0:
            try:
                am.mark_emitted_safe(key_str)
            except Exception:
                pass
    except Exception:
        pass


def dispatch(event: str, payload: JsonDict) -> HookResponse:
    """Dispatch event to appropriate handler and return response.

    Args:
        event: Hook event type (e.g., "SessionStart", "PreToolUse")
        payload: JSON-serializable dict containing event data

    Returns:
        Hook response dict with at least {"continue": bool}
    """
    handlers = _get_handlers()
    handler = handlers.get(event)
    if handler is None:
        return {"continue": True}

    # Build a tiny context object expected by handlers
    class Ctx:
        """Minimal context object for handler functions."""
        def __init__(self, event_type: str, payload: JsonDict) -> None:
            self.event_type: str = event_type
            self.payload: JsonDict = payload
            self.decision_api: object | None = None  # handlers create/own DecisionAPI if needed

    ctx = Ctx(event, payload)
    try:
        result = handler(ctx)
    except Exception:
        return {"continue": True}

    # Access result attributes directly (HandlerResult is known type)
    audio_type = None if result.suppress_audio else (result.audio_type or event)
    throttle_key = result.throttle_key
    throttle_window = result.throttle_window
    _play_audio(audio_type, throttle_key, throttle_window)

    # Build response with proper type
    response: HookResponse = {"continue": result.continue_value}

    # Map decision payload to hookSpecificOutput like herald did
    dp = result.decision_payload
    if dp:
        if event == constants.PRE_TOOL_USE:
            hook_output: JsonDict = {
                "hookEventName": event,
                "permissionDecision": dp.get("permissionDecision", "allow"),
            }
            if "permissionDecisionReason" in dp:
                hook_output["permissionDecisionReason"] = dp["permissionDecisionReason"]
            response["hookSpecificOutput"] = hook_output

        elif event in (constants.POST_TOOL_USE, constants.USER_PROMPT_SUBMIT, constants.SESSION_START, constants.SESSION_END):
            addl: object = dp.get("additionalContext", "")  # type: ignore[assignment]  # dp is dict[str, object]
            addl_str: str = ""
            if isinstance(addl, (dict, list)):
                try:
                    addl_str = json.dumps(addl, ensure_ascii=True)
                except Exception:
                    addl_str = ""
            elif isinstance(addl, str):
                addl_str = addl
            response["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": addl_str}

        if dp.get("decision") and event == constants.USER_PROMPT_SUBMIT:
            decision_value = dp.get("decision")
            if decision_value:
                response["decision"] = decision_value
            reason_value = dp.get("reason")
            if reason_value:
                response["reason"] = reason_value

    # If handler already injected hookSpecificOutput (e.g. session start/end code path) keep it
    if not response.get("hookSpecificOutput") and "hookSpecificOutput" in result.response:
        response["hookSpecificOutput"] = result.response["hookSpecificOutput"]

    return response


def main() -> int:
    """Main entry point for herald dispatcher.

    Parses CLI arguments, reads JSON payload from stdin, dispatches to handler,
    and outputs JSON response.

    Returns:
        Exit code (always 0)
    """
    ap = argparse.ArgumentParser(description="Herald dispatcher (Linus-style simplified)")
    _ = ap.add_argument("--hook", required=True, type=str, help="Hook event name")
    # --enable-audio is ignored; playback is decided inside AudioManager/config
    _ = ap.add_argument("--enable-audio", action="store_true", help="Enable audio (deprecated)")
    args = ap.parse_args()

    # Type-safe access to args (argparse returns Any for namespace attributes)
    hook_name: str = str(args.hook) if args.hook else ""  # type: ignore[attr-defined]
    payload = _read_stdin()
    out = dispatch(hook_name, payload)

    try:
        print(json.dumps(out))
    except Exception:
        print('{"continue": true}')
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
