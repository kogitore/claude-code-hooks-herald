#!/usr/bin/env python3
"""Unified dispatcher entry point for Claude Code audio hooks.

This script introduces the HeraldDispatcher class, responsible for routing
incoming Claude Code hook events through a shared middleware chain and then to
event-specific handlers. It intentionally keeps behaviour conservative so that
existing audio hooks can be migrated incrementally in later CORE tasks.

Key behaviours implemented for CORE-001:
- Shared registration API for handlers and middleware.
- Middleware execution with fail-safe error capture.
- Audio dispatch using the existing AudioManager (throttled by default).
- CLI interface (`--hook`) that preserves the JSON output contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, MutableMapping, Optional, Protocol, Tuple

from utils import constants
from utils.audio_manager import AudioManager
from utils.common_io import generate_audio_notes, parse_stdin
from utils.decision_api import DecisionAPI
from notification import handle_notification
from post_tool_use import PostToolUseHook, handle_post_tool_use
from pre_tool_use import PreToolUseHook, handle_pre_tool_use
from session_end import handle_session_end, SessionEndHook
from session_start import handle_session_start, SessionStartHook
from stop import handle_stop
from user_prompt_submit import UserPromptSubmitHook, handle_user_prompt_submit


# ---------------------------------------------------------------------------
# Type definitions


class HandlerCallable(Protocol):
    """Callable signature for event handlers registered on the dispatcher."""

    def __call__(self, context: "DispatchContext") -> "HandlerResult | None":
        ...  # pragma: no cover - Protocol definition only


class MiddlewareCallable(Protocol):
    """Callable signature for middleware executed prior to handler dispatch."""

    def __call__(self, context: "DispatchContext") -> "DispatchContext | None":
        ...  # pragma: no cover - Protocol definition only


@dataclass
class DispatchContext:
    """Mutable context object shared across middleware and handlers."""

    event_type: str
    payload: Dict[str, Any]
    marker: Optional[str] = None
    enable_audio: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    audio_type: Optional[str] = None
    throttle_key: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stop_dispatch: bool = False
    decision_api: Optional[DecisionAPI] = None

    def set_audio(self, audio_type: Optional[str], *, throttle_key: Optional[str] = None) -> None:
        self.audio_type = audio_type
        if throttle_key is not None:
            self.throttle_key = throttle_key


@dataclass
class HandlerResult:
    """Return type for event handlers."""

    response: Dict[str, Any] = field(default_factory=dict)
    audio_type: Optional[str] = None
    throttle_key: Optional[str] = None
    throttle_window: Optional[int] = None
    continue_value: bool = True
    notes: List[str] = field(default_factory=list)
    decision_payload: Optional[Dict[str, Any]] = None
    blocked: bool = False
    suppress_audio: bool = False


@dataclass
class DispatchReport:
    """Summarised outcome after running middleware, handler, and audio."""

    event_type: str
    handler_name: Optional[str]
    handled: bool
    audio_type: Optional[str]
    audio_played: bool
    audio_path: Optional[Path]
    throttled: bool
    response: Dict[str, Any]
    notes: List[str]
    errors: List[str]
    decision_payload: Optional[Dict[str, Any]]
    blocked: bool


# HandlerEntry 已移動到 utils.handler_registry


DEFAULT_THROTTLE_WINDOWS: MutableMapping[str, int] = {
    constants.NOTIFICATION: 30,
    constants.STOP: 600,
    constants.SUBAGENT_STOP: 600,
    constants.PRE_TOOL_USE: 60,
    constants.POST_TOOL_USE: 45,
    constants.SESSION_START: 5,
    constants.SESSION_END: 5,
    constants.USER_PROMPT_SUBMIT: 10,
}


def _default_throttle_key(context: DispatchContext, audio_type: Optional[str]) -> str:
    base = audio_type or context.event_type
    if context.event_type.lower() == "notification":
        message = context.payload.get("message") if isinstance(context.payload, dict) else None
        if isinstance(message, str) and message.strip():
            digest = hashlib.sha1(message.encode("utf-8")).hexdigest()[:12]
            return f"Notification:{digest}"
    marker = context.marker or "default"
    return f"{base}:{marker}"


class HeraldDispatcher:
    """Central dispatcher for Claude Code hook events."""

    def __init__(
        self,
        *,
        audio_manager: Optional[AudioManager] = None,
        decision_api: Optional[DecisionAPI] = None,
    ):
        self.audio_manager = audio_manager or AudioManager()
        self.decision_api = decision_api or DecisionAPI()
        
        # Simple handler dictionary - no registry pattern bullshit
        self.event_handlers: Dict[str, HandlerCallable] = {}
        self.middleware_chain: List[Any] = []  # Unused but kept for compatibility

    # -- Registration (委派給 HandlerRegistry) -------------------------------
    def register_handler(
        self,
        event_type: str,
        handler: HandlerCallable,
        *,
        name: Optional[str] = None,
        audio_type: Optional[str] = None,
        throttle_window: Optional[int] = None,
        throttle_key_factory: Optional[Callable[[DispatchContext], Optional[str]]] = None,
    ) -> None:
        """Simple handler registration - just store in dictionary"""
        self.event_handlers[event_type] = handler

    def register_middleware(self, middleware: Any, *, name: Optional[str] = None) -> None:
        """Middleware registration - ignored for now, will be removed in Phase 3"""
        pass  # Middleware is bullshit - ignore it

    # -- Dispatch ---------------------------------------------------------
    def dispatch(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        marker: Optional[str] = None,
        enable_audio: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DispatchReport:
        payload = payload or {}
        metadata = metadata or {}
        context = DispatchContext(
            event_type=event_type,
            payload=payload,
            marker=marker,
            enable_audio=enable_audio,
            metadata=metadata,
            decision_api=self.decision_api,
        )

        # Direct handler lookup and invocation (no middleware/registry bullshit)
        handler = self.event_handlers.get(event_type)
        handler_name = getattr(handler, "__name__", None)
        handled = False
        handler_response = HandlerResult()

        if handler and not context.stop_dispatch:
            try:
                maybe_response = handler(context)
                if isinstance(maybe_response, HandlerResult):
                    handler_response = maybe_response
                elif isinstance(maybe_response, dict):
                    handler_response.response.update(maybe_response)
                handled = True
            except Exception as exc:  # pragma: no cover - defensive path
                context.errors.append(f"handler:{handler_name or 'unknown'} - {exc}")

        # Resolve audio type and throttling window
        resolved_audio_type = handler_response.audio_type or context.audio_type or event_type
        if handler_response.suppress_audio:
            resolved_audio_type = None

        throttle_window = handler_response.throttle_window
        if throttle_window is None:
            throttle_window = DEFAULT_THROTTLE_WINDOWS.get(resolved_audio_type or "", 0)

        throttle_key = handler_response.throttle_key or context.throttle_key or _default_throttle_key(context, resolved_audio_type)

        # Perform audio playback directly via AudioManager with throttling
        audio_played = False
        audio_path = None
        throttled = False
        if resolved_audio_type:
            # Check throttle
            if throttle_window > 0 and throttle_key:
                throttled = self.audio_manager.should_throttle_safe(throttle_key, throttle_window)
            if not throttled:
                played, path, _ctx = self.audio_manager.play_audio_safe(resolved_audio_type, enabled=enable_audio, additional_context={
                    "eventType": event_type,
                    "marker": marker,
                })
                audio_played = played
                audio_path = path
                # Mark emission only if we acted
                if throttle_window > 0 and throttle_key:
                    self.audio_manager.mark_emitted_safe(throttle_key)
            # Notes for debug
            context.notes.extend(generate_audio_notes(
                throttled=throttled,
                path=audio_path,
                played=audio_played,
                enabled=enable_audio,
                throttle_msg=f"Throttled {resolved_audio_type} for {throttle_window}s"
            ))
        # Handler notes
        context.notes.extend(handler_response.notes)

        response = {"continue": handler_response.continue_value}
        response.update(handler_response.response)

        # Format response according to Claude Code schema
        # Only include schema-compliant fields in the final response
        if handler_response.decision_payload:
            decision_data = handler_response.decision_payload

            if event_type == constants.PRE_TOOL_USE:
                # PreToolUse specific schema
                response["hookSpecificOutput"] = {
                    "hookEventName": constants.PRE_TOOL_USE,
                    "permissionDecision": decision_data.get("permissionDecision", "allow")
                }
                if "permissionDecisionReason" in decision_data:
                    response["hookSpecificOutput"]["permissionDecisionReason"] = decision_data["permissionDecisionReason"]

            elif event_type == constants.USER_PROMPT_SUBMIT:
                # UserPromptSubmit specific schema
                response["hookSpecificOutput"] = {
                    "hookEventName": constants.USER_PROMPT_SUBMIT,
                    "additionalContext": decision_data.get("additionalContext", "")
                }
            else:
                # For other events that have decision logic (PostToolUse, etc.)
                # Stop and SubagentStop should remain simple and not include decision fields
                pass

        # Ensure only schema-compliant top-level fields are present
        schema_fields = {"continue", "suppressOutput", "stopReason", "systemMessage", "decision", "reason", "hookSpecificOutput"}
        response = {k: v for k, v in response.items() if k in schema_fields}

        # Map decision values to Claude Code schema requirements
        return DispatchReport(
            event_type=event_type,
            handler_name=handler_name,
            handled=handled,
            audio_type=resolved_audio_type,
            audio_played=audio_played,
            audio_path=audio_path,
            throttled=throttled,
            response=response,
            notes=context.notes,
            errors=context.errors,
            decision_payload=handler_response.decision_payload,
            blocked=handler_response.blocked,
        )


# ---------------------------------------------------------------------------
# CLI interface


def _emit_report(report: DispatchReport) -> None:
    try:
        parts = [
            f"[Herald] event={report.event_type}",
            f"handler={report.handler_name or 'none'}",
            f"handled={report.handled}",
            f"audio={report.audio_type}",
            f"played={report.audio_played}",
            f"throttled={report.throttled}",
        ]
        if report.audio_path:
            parts.append(f"path={report.audio_path}")
        if report.notes:
            parts.append(f"notes={'|'.join(report.notes)}")
        if report.errors:
            parts.append(f"errors={'|'.join(report.errors)}")
        if report.decision_payload:
            decision = report.decision_payload.get("permissionDecision") or report.decision_payload.get("decision")
            if decision:
                parts.append(f"decision={decision}")
        if report.blocked:
            parts.append("blocked=True")
        print(" ".join(parts), file=sys.stderr)
    except Exception:  # pragma: no cover - defensive logging
        pass


def build_default_dispatcher(
    *,
    audio_manager: Optional[AudioManager] = None,
    decision_api: Optional[DecisionAPI] = None,
) -> HeraldDispatcher:
    dispatcher = HeraldDispatcher(audio_manager=audio_manager, decision_api=decision_api)

    # Function-based simple handlers
    pre_tool_use_hook = handle_pre_tool_use
    post_tool_use_hook = handle_post_tool_use
    session_start_hook = handle_session_start
    session_end_hook = handle_session_end
    user_prompt_hook = handle_user_prompt_submit

    def _decision_api_for(context: DispatchContext) -> DecisionAPI:
        return context.decision_api or dispatcher.decision_api

    def _apply_decision(hr: HandlerResult, decision_response) -> None:
        if decision_response is None:
            return
        hr.decision_payload = decision_response.to_dict()
        hr.blocked = getattr(decision_response, "blocked", False)

    def _hook_handler(event_name: str, hook_instance):
        def handler(context: DispatchContext) -> HandlerResult:
            # If hook_instance is a function, call directly
            if callable(hook_instance):
                maybe = hook_instance(context)
                if isinstance(maybe, HandlerResult):
                    return maybe
            # Fallback for class-based hooks still using BaseHook
            if hasattr(hook_instance, "execute"):
                result = hook_instance.execute(
                    context.payload,
                    enable_audio=context.enable_audio,
                    parsed_args=context.metadata.get("argv"),
                )
                hr = HandlerResult()
                hr.continue_value = getattr(result, "continue_value", True)
                if getattr(result, "payload", None):
                    hr.response.update(result.payload)
                hr.audio_type = getattr(result, "audio_type", None) or event_name
                hr.throttle_key = getattr(result, "throttle_key", None)
                hr.throttle_window = getattr(result, "throttle_window", None)
                if getattr(result, "notes", None):
                    hr.notes.extend(result.notes)
                if getattr(result, "errors", None):
                    context.errors.extend(result.errors)
                # Try to capture decision payload if present
                last_decision = getattr(hook_instance, "_last_decision", None)
                if last_decision is not None and hasattr(last_decision, "to_dict"):
                    hr.decision_payload = last_decision.to_dict()
                    hr.blocked = getattr(last_decision, "blocked", False)
                return hr
            return HandlerResult()

        return handler

    def _stop_handler(context: DispatchContext, hook_instance) -> HandlerResult:
        api = _decision_api_for(context)
        decision = api.stop_decision(context.payload)
        hr = HandlerResult()
        _apply_decision(hr, decision)

        # Preserve audio-related properties from the original hook if needed
        result = hook_instance.execute(context.payload, enable_audio=context.enable_audio)
        hr.audio_type = result.audio_type or context.event_type
        hr.throttle_key = result.throttle_key
        hr.throttle_window = result.throttle_window
        return hr

    dispatcher.register_handler(constants.NOTIFICATION, _hook_handler(constants.NOTIFICATION, handle_notification), audio_type=constants.NOTIFICATION)
    dispatcher.register_handler(constants.STOP, _hook_handler(constants.STOP, handle_stop), audio_type=constants.STOP)
    dispatcher.register_handler(constants.SUBAGENT_STOP, _hook_handler(constants.SUBAGENT_STOP, handle_stop), audio_type=constants.SUBAGENT_STOP)
    dispatcher.register_handler(constants.PRE_TOOL_USE, _hook_handler(constants.PRE_TOOL_USE, pre_tool_use_hook), audio_type=constants.PRE_TOOL_USE)
    dispatcher.register_handler(constants.POST_TOOL_USE, _hook_handler(constants.POST_TOOL_USE, post_tool_use_hook), audio_type=constants.POST_TOOL_USE)
    dispatcher.register_handler(constants.SESSION_START, _hook_handler(constants.SESSION_START, handle_session_start), audio_type=constants.SESSION_START)
    dispatcher.register_handler(constants.SESSION_END, _hook_handler(constants.SESSION_END, handle_session_end), audio_type=constants.SESSION_END)
    dispatcher.register_handler(constants.USER_PROMPT_SUBMIT, _hook_handler(constants.USER_PROMPT_SUBMIT, user_prompt_hook), audio_type=constants.USER_PROMPT_SUBMIT)

    def _noop_handler(_: DispatchContext) -> HandlerResult:
        hr = HandlerResult()
        hr.suppress_audio = True
        return hr

    dispatcher.register_handler(constants.PRE_COMPACT, _noop_handler, audio_type=None)

    return dispatcher


def _extract_tool_name(payload: Dict[str, Any]) -> str:
    for key in ("toolName", "tool_name", "tool", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "unknown"


def _extract_tool_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    # 支援Claude Code標準欄位名稱
    candidate = (payload.get("toolInput") or
                 payload.get("tool_input") or
                 payload.get("input") or
                 payload.get("args"))
    if isinstance(candidate, dict):
        return candidate
    if isinstance(candidate, (list, tuple)):
        return {"args": list(candidate)}
    if isinstance(candidate, str):
        return {"command": candidate}
    return payload if isinstance(payload, dict) else {}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Claude Code Herald dispatcher")
    parser.add_argument("--hook", required=True, help="Claude Code hook event name")
    parser.add_argument("--enable-audio", action="store_true", help="Enable real audio playback")
    parser.add_argument("--json-only", action="store_true", help="Reserved for compatibility; no-op")
    args = parser.parse_args(argv)

    payload, marker = parse_stdin()
    dispatcher = build_default_dispatcher()

    report = dispatcher.dispatch(
        args.hook,
        payload=payload,
        marker=marker,
        enable_audio=args.enable_audio,
        metadata={"argv": argv or sys.argv[1:]},
    )

    _emit_report(report)

    try:
        print(json.dumps(report.response))
    except Exception:  # pragma: no cover - defensive path
        # Ensure JSON output contract is never broken
        print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
