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

from utils.audio_manager import AudioManager
from utils.common_io import generate_audio_notes, parse_stdin
from utils.decision_api import DecisionAPI
from notification import NotificationHook
from stop import StopHook
from subagent_stop import SubagentStopHook


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


@dataclass
class HandlerEntry:
    """Registration metadata for a handler."""

    handler: HandlerCallable
    name: str
    audio_type: Optional[str] = None
    throttle_window: Optional[int] = None
    throttle_key_factory: Optional[Callable[[DispatchContext], Optional[str]]] = None


DEFAULT_THROTTLE_WINDOWS: MutableMapping[str, int] = {
    "Notification": 30,
    "Stop": 600,
    "SubagentStop": 600,
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
        self.event_handlers: Dict[str, HandlerEntry] = {}
        self.middleware_chain: List[Tuple[str, MiddlewareCallable]] = []
        self.audio_manager = audio_manager or AudioManager()
        self.decision_api = decision_api or DecisionAPI()

    # -- Registration -----------------------------------------------------
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
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type must be a non-empty string")
        entry = HandlerEntry(
            handler=handler,
            name=name or handler.__name__,
            audio_type=audio_type,
            throttle_window=throttle_window,
            throttle_key_factory=throttle_key_factory,
        )
        self.event_handlers[event_type] = entry

    def register_middleware(self, middleware: MiddlewareCallable, *, name: Optional[str] = None) -> None:
        self.middleware_chain.append((name or middleware.__name__, middleware))

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

        handler_entry = self.event_handlers.get(event_type)
        handler_name = handler_entry.name if handler_entry else None

        # Pre-handler middleware execution
        for mw_name, middleware in self.middleware_chain:
            try:
                result = middleware(context)
                if isinstance(result, DispatchContext):
                    context = result
            except Exception as exc:  # pragma: no cover - defensive path
                context.errors.append(f"middleware:{mw_name} - {exc}")
            if context.stop_dispatch:
                break

        handled = False
        handler_response = HandlerResult()

        if not context.stop_dispatch and handler_entry:
            try:
                maybe_response = handler_entry.handler(context)
                if isinstance(maybe_response, HandlerResult):
                    handler_response = maybe_response
                elif isinstance(maybe_response, dict):
                    handler_response.response.update(maybe_response)
                handled = True
            except Exception as exc:  # pragma: no cover - defensive path
                context.errors.append(f"handler:{handler_entry.name} - {exc}")

        resolved_audio_type = (
            handler_response.audio_type
            or context.audio_type
            or (handler_entry.audio_type if handler_entry else None)
            or event_type
        )
        if handler_response.suppress_audio:
            resolved_audio_type = None

        throttle_window = handler_response.throttle_window
        if throttle_window is None and handler_entry:
            throttle_window = handler_entry.throttle_window
        if throttle_window is None:
            throttle_window = DEFAULT_THROTTLE_WINDOWS.get(resolved_audio_type or "", 0)

        throttle_key = (
            handler_response.throttle_key
            or context.throttle_key
            or (handler_entry.throttle_key_factory(context) if handler_entry and handler_entry.throttle_key_factory else None)
        )
        if not throttle_key and resolved_audio_type:
            throttle_key = _default_throttle_key(context, resolved_audio_type)

        audio_played = False
        audio_path: Optional[Path] = None
        throttled = False

        if resolved_audio_type and not context.stop_dispatch and not handler_response.suppress_audio:
            throttle_window = int(throttle_window or 0)
            throttle_key = throttle_key or _default_throttle_key(context, resolved_audio_type)
            window = self.audio_manager.get_throttle_window(resolved_audio_type, throttle_window)
            if window > 0 and throttle_key:
                throttled = self.audio_manager.should_throttle(throttle_key, window)
            if not throttled:
                audio_played, audio_path = self.audio_manager.play_audio(resolved_audio_type, enabled=enable_audio)
                if throttle_key:
                    self.audio_manager.mark_emitted(throttle_key)
            context.notes.extend(
                generate_audio_notes(
                    throttled=throttled,
                    path=audio_path,
                    played=audio_played,
                    enabled=enable_audio,
                    throttle_msg=f"Throttled (<= {window}s)",
                )
            )

        context.notes.extend(handler_response.notes)

        response = {"continue": handler_response.continue_value}
        response.update(handler_response.response)

        # Format response according to Claude Code schema
        # Only include schema-compliant fields in the final response
        if handler_response.decision_payload:
            decision_data = handler_response.decision_payload

            if event_type == "PreToolUse":
                # PreToolUse specific schema
                response["hookSpecificOutput"] = {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision_data.get("permissionDecision", "allow")
                }
                if "permissionDecisionReason" in decision_data:
                    response["hookSpecificOutput"]["permissionDecisionReason"] = decision_data["permissionDecisionReason"]

            elif event_type == "UserPromptSubmit":
                # UserPromptSubmit specific schema
                response["hookSpecificOutput"] = {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": decision_data.get("additionalContext", "")
                }
            else:
                # For other events that have decision logic (PostToolUse, etc.)
                # Stop and SubagentStop should remain simple and not include decision fields
                pass

        # Ensure only schema-compliant top-level fields are present
        schema_fields = {"continue", "suppressOutput", "stopReason", "decision", "reason", "systemMessage", "permissionDecision", "hookSpecificOutput"}
        response = {k: v for k, v in response.items() if k in schema_fields}

        # Map decision values to Claude Code schema requirements
        if "decision" in response:
            if response["decision"] == "allow":
                response["decision"] = "approve"
            # "block" remains "block" as it's already correct

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

    notification_hook = NotificationHook(audio_manager=dispatcher.audio_manager)
    stop_hook = StopHook(audio_manager=dispatcher.audio_manager)
    subagent_hook = SubagentStopHook(audio_manager=dispatcher.audio_manager)

    def _decision_api_for(context: DispatchContext) -> DecisionAPI:
        return context.decision_api or dispatcher.decision_api

    def _apply_decision(hr: HandlerResult, decision_response) -> None:
        if decision_response is None:
            return
        hr.decision_payload = decision_response.to_dict()
        hr.blocked = getattr(decision_response, "blocked", False)

    def _hook_handler(event_name: str, hook_instance):
        def handler(context: DispatchContext) -> HandlerResult:
            result = hook_instance.execute(context.payload, enable_audio=False)
            hr = HandlerResult()
            hr.continue_value = result.continue_value
            hr.response.update(result.payload)
            hr.audio_type = result.audio_type or event_name
            hr.throttle_key = result.throttle_key
            hr.throttle_window = result.throttle_window
            return hr

        return handler

    def _stop_handler(context: DispatchContext, hook_instance) -> HandlerResult:
        api = _decision_api_for(context)
        decision = api.stop_decision(context.payload)
        hr = HandlerResult()
        _apply_decision(hr, decision)

        # Preserve audio-related properties from the original hook if needed
        result = hook_instance.execute(context.payload, enable_audio=False)
        hr.audio_type = result.audio_type or context.event_type
        hr.throttle_key = result.throttle_key
        hr.throttle_window = result.throttle_window
        return hr

    def _pre_tool_use_handler(context: DispatchContext) -> HandlerResult:
        api = _decision_api_for(context)
        payload = context.payload if isinstance(context.payload, dict) else {}
        decision = api.pre_tool_use_decision(_extract_tool_name(payload), _extract_tool_input(payload))
        hr = HandlerResult()
        _apply_decision(hr, decision)
        hr.suppress_audio = True
        return hr

    def _post_tool_use_handler(context: DispatchContext) -> HandlerResult:
        api = _decision_api_for(context)
        payload = context.payload if isinstance(context.payload, dict) else {}
        decision = api.post_tool_use_decision(_extract_tool_name(payload), payload)
        hr = HandlerResult()
        _apply_decision(hr, decision)
        hr.suppress_audio = True
        return hr

    dispatcher.register_handler("Notification", _hook_handler("Notification", notification_hook), audio_type=None)
    dispatcher.register_handler("Stop", lambda ctx: _stop_handler(ctx, stop_hook), audio_type=None)
    dispatcher.register_handler(
        "SubagentStop",
        lambda ctx: _stop_handler(ctx, subagent_hook),
        audio_type=None,
    )
    dispatcher.register_handler("PreToolUse", _pre_tool_use_handler, audio_type=None)
    dispatcher.register_handler("PostToolUse", _post_tool_use_handler, audio_type=None)

    def _noop_handler(_: DispatchContext) -> HandlerResult:
        hr = HandlerResult()
        hr.suppress_audio = True
        return hr

    for evt in ("UserPromptSubmit", "SessionStart", "SessionEnd", "PreCompact"):
        dispatcher.register_handler(evt, _noop_handler, audio_type=None)

    return dispatcher


def _extract_tool_name(payload: Dict[str, Any]) -> str:
    for key in ("toolName", "tool_name", "tool", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "unknown"


def _extract_tool_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    candidate = payload.get("toolInput") or payload.get("input") or payload.get("args")
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
