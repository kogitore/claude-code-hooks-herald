#!/usr/bin/env python3
"""Ultra-minimal dispatcher (herald deprecation path).

Maps hook event -> handler function. Provides:
 - stdin JSON parse (best effort)
 - audio via existing HandlerResult fields
 - standard JSON response contract

No middleware. No registry. No ceremony.
"""
from __future__ import annotations

import json, sys, argparse
from typing import Any, Dict, Callable, Optional
from pathlib import Path

from utils import constants
from utils.audio_manager import AudioManager  # reuse until we swap to simple

# Import handlers (already function-based)
from notification import handle_notification
from stop import handle_stop, handle_subagent_stop
from pre_tool_use import handle_pre_tool_use
from post_tool_use import handle_post_tool_use
from session_start import handle_session_start
from session_end import handle_session_end
from user_prompt_submit import handle_user_prompt_submit


class HandlerResult:  # minimal shim (subset used by handlers)
    def __init__(self):
        self.response: Dict[str, Any] = {}
        self.audio_type: Optional[str] = None
        self.throttle_key: Optional[str] = None
        self.throttle_window: Optional[int] = None
        self.continue_value: bool = True
        self.decision_payload: Optional[Dict[str, Any]] = None
        self.suppress_audio: bool = False


HANDLERS: Dict[str, Callable[[Any], HandlerResult]] = {
    constants.NOTIFICATION: handle_notification,
    constants.STOP: handle_stop,
    constants.SUBAGENT_STOP: handle_subagent_stop,
    constants.PRE_TOOL_USE: handle_pre_tool_use,
    constants.POST_TOOL_USE: handle_post_tool_use,
    constants.SESSION_START: handle_session_start,
    constants.SESSION_END: handle_session_end,
    constants.USER_PROMPT_SUBMIT: handle_user_prompt_submit,
}


def _read_stdin() -> Dict[str, Any]:
    try:
        raw = sys.stdin.read().strip() or "{}"
        return json.loads(raw)
    except Exception:
        return {}


def _play_audio(audio_type: Optional[str], enable: bool) -> None:
    if not audio_type:
        return
    try:
        am = AudioManager()
        am.play_audio_safe(audio_type, enabled=enable)
    except Exception:
        pass


def dispatch(event: str, payload: Dict[str, Any], enable_audio: bool) -> Dict[str, Any]:
    handler = HANDLERS.get(event)
    if handler is None:
        return {"continue": True}
    # Build a tiny context object expected by handlers
    class Ctx:
        def __init__(self, event_type: str, payload: Dict[str, Any]):
            self.event_type = event_type
            self.payload = payload
            self.decision_api = None  # handlers create/own DecisionAPI if needed
    ctx = Ctx(event, payload)
    try:
        result = handler(ctx)
    except Exception:
        return {"continue": True}

    audio_type = None if getattr(result, 'suppress_audio', False) else (result.audio_type or event)
    _play_audio(audio_type, enable_audio)

    response = {"continue": getattr(result, 'continue_value', True)}
    # Map decision payload to hookSpecificOutput like herald did
    dp = getattr(result, 'decision_payload', None)
    if dp:
        if event == constants.PRE_TOOL_USE:
            response["hookSpecificOutput"] = {
                "hookEventName": event,
                "permissionDecision": dp.get("permissionDecision", "allow"),
            }
            if "permissionDecisionReason" in dp:
                response["hookSpecificOutput"]["permissionDecisionReason"] = dp["permissionDecisionReason"]
        elif event in (constants.POST_TOOL_USE, constants.USER_PROMPT_SUBMIT, constants.SESSION_START, constants.SESSION_END):
            addl = dp.get("additionalContext", "")
            if isinstance(addl, (dict, list)):
                try:
                    addl = json.dumps(addl, ensure_ascii=False)
                except Exception:
                    addl = ""
            response["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": addl}
        if dp.get("decision") and event == constants.USER_PROMPT_SUBMIT:
            response["decision"] = dp.get("decision")
            if dp.get("reason"):
                response["reason"] = dp.get("reason")
    # If handler already injected hookSpecificOutput (e.g. session start/end code path) keep it
    if not response.get("hookSpecificOutput") and isinstance(result.response, dict):
        if "hookSpecificOutput" in result.response:
            response["hookSpecificOutput"] = result.response["hookSpecificOutput"]
    return response


def main() -> int:
    ap = argparse.ArgumentParser(description="Mini dispatcher (herald replacement)")
    ap.add_argument("--hook", required=True)
    ap.add_argument("--enable-audio", action="store_true")
    args = ap.parse_args()
    payload = _read_stdin()
    out = dispatch(args.hook, payload, args.enable_audio)
    try:
        print(json.dumps(out))
    except Exception:
        print('{"continue": true}')
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
