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
from utils.audio_dispatcher import AudioDispatcher
from utils.middleware_runner import MiddlewareRunner
from utils.common_io import generate_audio_notes, parse_stdin
from utils.decision_api import DecisionAPI
from utils.handler_registry import HandlerRegistry, HandlerEntry
from notification import NotificationHook
from post_tool_use import PostToolUseHook
from pre_tool_use import PreToolUseHook
from session_end import SessionEndHook
from session_start import SessionStartHook
from stop import StopHook
from subagent_stop import SubagentStopHook
from user_prompt_submit import UserPromptSubmitHook


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
        self.handler_registry = HandlerRegistry()  # 新增：處理器註冊管理器
        self.audio_manager = audio_manager or AudioManager()
        self.audio_dispatcher = AudioDispatcher(self.audio_manager)
        self.middleware_runner = MiddlewareRunner()  # 新增：中間件執行引擎
        self.decision_api = decision_api or DecisionAPI()
        
        # 保持向後兼容性的屬性
        self.event_handlers = self.handler_registry.event_handlers
        self.middleware_chain = self.handler_registry.middleware_chain

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
        """委派處理器註冊到 HandlerRegistry"""
        return self.handler_registry.register_handler(
            event_type, 
            handler, 
            name=name, 
            audio_type=audio_type,
            throttle_window=throttle_window, 
            throttle_key_factory=throttle_key_factory
        )

    def register_middleware(self, middleware: MiddlewareCallable, *, name: Optional[str] = None) -> None:
        """委派中間件註冊到 HandlerRegistry"""
        return self.handler_registry.register_middleware(middleware, name=name)

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
        context = self.middleware_runner.run_middleware(self.middleware_chain, context)

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
        # 使用 AudioDispatcher 處理音頻邏輯 (階段 1 重構)
        audio_report = self.audio_dispatcher.handle_audio(
            context, 
            handler_response, 
            enable_audio=enable_audio
        )
        
        # 從 AudioReport 提取兼容的變數（向後兼容）
        audio_played = audio_report.played
        audio_path = audio_report.audio_path
        throttled = audio_report.throttled
        resolved_audio_type = audio_report.resolved_audio_type
        
        # 將音頻註記和錯誤添加到 context
        context.notes.extend(audio_report.notes)
        context.errors.extend(audio_report.errors)

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

    notification_hook = NotificationHook(audio_manager=dispatcher.audio_manager)
    stop_hook = StopHook(audio_manager=dispatcher.audio_manager)
    subagent_hook = SubagentStopHook(audio_manager=dispatcher.audio_manager)
    pre_tool_use_hook = PreToolUseHook(
        audio_manager=dispatcher.audio_manager,
        decision_api=dispatcher.decision_api,
    )
    post_tool_use_hook = PostToolUseHook(
        audio_manager=dispatcher.audio_manager,
        decision_api=dispatcher.decision_api,
    )
    session_start_hook = SessionStartHook(audio_manager=dispatcher.audio_manager)
    session_end_hook = SessionEndHook(audio_manager=dispatcher.audio_manager)
    user_prompt_hook = UserPromptSubmitHook(audio_manager=dispatcher.audio_manager)

    def _decision_api_for(context: DispatchContext) -> DecisionAPI:
        return context.decision_api or dispatcher.decision_api

    def _apply_decision(hr: HandlerResult, decision_response) -> None:
        if decision_response is None:
            return
        hr.decision_payload = decision_response.to_dict()
        hr.blocked = getattr(decision_response, "blocked", False)

    def _hook_handler(event_name: str, hook_instance):
        def handler(context: DispatchContext) -> HandlerResult:
            result = hook_instance.execute(
                context.payload,
                enable_audio=context.enable_audio,
                parsed_args=context.metadata.get("argv"),
            )
            hr = HandlerResult()
            hr.continue_value = result.continue_value
            hr.response.update(result.payload)
            hr.audio_type = result.audio_type or event_name
            hr.throttle_key = result.throttle_key
            hr.throttle_window = result.throttle_window
            hr.notes.extend(result.notes)
            if result.errors:
                context.errors.extend(result.errors)

            last_decision = getattr(hook_instance, "_last_decision", None)
            if last_decision is not None and hasattr(last_decision, "to_dict"):
                hr.decision_payload = last_decision.to_dict()
                hr.blocked = getattr(last_decision, "blocked", False)
            return hr

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

    dispatcher.register_handler(constants.NOTIFICATION, _hook_handler(constants.NOTIFICATION, notification_hook), audio_type=constants.NOTIFICATION)
    dispatcher.register_handler(constants.STOP, lambda ctx: _stop_handler(ctx, stop_hook), audio_type=constants.STOP)
    dispatcher.register_handler(constants.SUBAGENT_STOP, lambda ctx: _stop_handler(ctx, subagent_hook), audio_type=constants.SUBAGENT_STOP)
    dispatcher.register_handler(constants.PRE_TOOL_USE, _hook_handler(constants.PRE_TOOL_USE, pre_tool_use_hook), audio_type=constants.PRE_TOOL_USE, throttle_window=pre_tool_use_hook.default_throttle_seconds)
    dispatcher.register_handler(constants.POST_TOOL_USE, _hook_handler(constants.POST_TOOL_USE, post_tool_use_hook), audio_type=constants.POST_TOOL_USE, throttle_window=post_tool_use_hook.default_throttle_seconds)
    dispatcher.register_handler(constants.SESSION_START, _hook_handler(constants.SESSION_START, session_start_hook), audio_type=constants.SESSION_START, throttle_window=session_start_hook.default_throttle_seconds)
    dispatcher.register_handler(constants.SESSION_END, _hook_handler(constants.SESSION_END, session_end_hook), audio_type=constants.SESSION_END, throttle_window=session_end_hook.default_throttle_seconds)
    dispatcher.register_handler(constants.USER_PROMPT_SUBMIT, _hook_handler(constants.USER_PROMPT_SUBMIT, user_prompt_hook), audio_type=constants.USER_PROMPT_SUBMIT, throttle_window=user_prompt_hook.default_throttle_seconds)

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
