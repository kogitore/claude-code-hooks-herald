#!/usr/bin/env python3
"""PreToolUse hook for Claude Code Decision API integration.

This hook is triggered BEFORE a tool is executed and implements the Decision API
to allow/deny/ask/block tool execution based on configurable security policies.

IMPLEMENTATION REQUIREMENTS for Codex:
1. Inherit from BaseHook with default_audio_event = "PreToolUse"
2. Implement handle_hook_logic() method that:
   - Extracts tool name and toolInput from context
   - Uses DecisionAPI.evaluate_pre_tool_use() for policy evaluation
   - Returns HookExecutionResult with decision API response format
3. Handle edge cases:
   - Missing tool/toolInput fields in context
   - Invalid JSON in tool parameters
   - DecisionAPI evaluation failures
4. Audio integration:
   - Only play audio for 'ask' or 'deny' decisions (not 'allow')
   - Use appropriate audio mapping from audio_config.json

DECISION API RESPONSE FORMAT:
{
    "decision": "allow|deny|ask|blockStop",
    "reason": "Human-readable explanation",
    "metadata": {...}  // Optional
}

CRITICAL NOTES:
- This is a SECURITY HOOK - failures should default to 'ask' or 'deny', never 'allow'
- Must handle tool parameter extraction carefully to avoid JSON injection
- Should log security decisions for audit purposes
- Decision policy is loaded from utils/decision_policy.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from utils.decision_api import DecisionAPI, DecisionResponse
from utils.constants import PRE_TOOL_USE


MAX_COMMAND_PREVIEW = 240


@dataclass
class PreToolUseAuditRecord:
    tool: str
    decision: str
    blocked: bool
    severity: Optional[str]
    tags: List[str]
    issues: List[str]
    preview: Optional[str]
    timestamp: str


def _extract_tool(context: Dict[str, Any]) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    tool = (
        context.get("tool")
        or context.get("toolName")
        or context.get("tool_name")
        or context.get("name")
    )
    if isinstance(tool, str) and tool.strip():
        return tool.strip(), warnings
    warnings.append("missing_tool_name")
    return "unknown", warnings


def _extract_tool_input(context: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str], Optional[str]]:
    warnings: List[str] = []
    preview: Optional[str] = None
    raw = context.get("toolInput") or context.get("tool_input") or context.get("input")

    if isinstance(raw, dict):
        preview = _preview_command(raw)
        return raw, warnings, preview
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                preview = _preview_command(parsed)
                return parsed, warnings, preview
            if isinstance(parsed, list):
                converted = {"args": parsed}
                preview = _preview_command(converted)
                return converted, warnings, preview
        except json.JSONDecodeError:
            warnings.append("invalid_tool_input_json")
            preview = raw[:MAX_COMMAND_PREVIEW]
            return None, warnings, preview
    if isinstance(raw, (list, tuple)):
        converted = {"args": [str(item) for item in raw]}
        preview = _preview_command(converted)
        return converted, warnings, preview

    if raw is not None:
        warnings.append("unsupported_tool_input_type")
        preview = str(raw)[:MAX_COMMAND_PREVIEW]

    command = context.get("command")
    if isinstance(command, str) and command.strip():
        preview = command[:MAX_COMMAND_PREVIEW]
        return {"command": command}, warnings, preview

    return None, warnings, preview


def _preview_command(payload: Dict[str, Any]) -> Optional[str]:
    command = payload.get("command")
    if isinstance(command, str) and command.strip():
        return command.strip()[:MAX_COMMAND_PREVIEW]
    args = payload.get("args")
    if isinstance(args, list):
        joined = " ".join(str(item) for item in args)
        if joined:
            return joined[:MAX_COMMAND_PREVIEW]
    return None


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Function-based simple handler for dispatcher ---------------------------
def handle_pre_tool_use(context) -> "HandlerResult":  # type: ignore[name-defined]
    """Function handler for PreToolUse with DecisionAPI security logic.

    Behaviour:
    - Extract tool name and toolInput from context.payload
    - Call DecisionAPI.pre_tool_use_decision(tool, tool_input)
    - If parsing issues exist, escalate to `ask`
    - Suppress audio on clean allow; play audio for ask/deny/block
    - Return HandlerResult with decision_payload for dispatcher mapping
    """
    from herald import HandlerResult  # local import to avoid circulars

    payload: Dict[str, Any] = context.payload if isinstance(context.payload, dict) else {}
    api: DecisionAPI = context.decision_api or DecisionAPI()

    # Minimal extraction mirroring class behaviour
    issues: List[str] = []

    # Tool name
    tool = (
        payload.get("tool")
        or payload.get("toolName")
        or payload.get("tool_name")
        or payload.get("name")
        or "unknown"
    )
    if not isinstance(tool, str) or not tool.strip():
        tool = "unknown"
        issues.append("missing_tool_name")

    # Tool input
    tool_input = None
    raw = payload.get("toolInput") or payload.get("tool_input") or payload.get("input")
    preview: Optional[str] = None
    if isinstance(raw, dict):
        tool_input = raw
        preview = _preview_command(raw)
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                tool_input = parsed
                preview = _preview_command(parsed)
            elif isinstance(parsed, list):
                tool_input = {"args": parsed}
                preview = _preview_command(tool_input)
            else:
                issues.append("unsupported_tool_input_type")
                preview = raw[:MAX_COMMAND_PREVIEW]
        except json.JSONDecodeError:
            issues.append("invalid_tool_input_json")
            preview = raw[:MAX_COMMAND_PREVIEW]
    elif isinstance(raw, (list, tuple)):
        tool_input = {"args": [str(x) for x in raw]}
        preview = _preview_command(tool_input)
    elif raw is not None:
        issues.append("unsupported_tool_input_type")
        preview = str(raw)[:MAX_COMMAND_PREVIEW]

    # Decision evaluation
    try:
        decision = api.pre_tool_use_decision(tool, tool_input)
    except Exception as exc:  # safety first
        decision = api.ask(
            "無法評估工具安全性，請人工確認",
            event=PRE_TOOL_USE,
            additional_context={"tool": tool, "error": type(exc).__name__},
            severity="high",
        )

    # Escalate ambiguous inputs to manual review
    if not decision.blocked and issues:
        decision = api.ask(
            "工具輸入格式不明確，請人工確認",
            event=PRE_TOOL_USE,
            additional_context={"tool": tool, "issues": issues},
            severity=decision.severity or "medium",
            tags=(decision.tags or []) + ["pretooluse:input-warning"],
        )

    # Build audit payload (lightweight; embedded into decision payload additionalContext)
    extra_ctx = decision.payload.setdefault("additionalContext", {})
    extra_ctx.setdefault("tool", tool)
    if issues:
        extra_ctx.setdefault("issues", issues)
    audit = {
        "decision": decision.payload.get("permissionDecision") or decision.payload.get("decision", "unknown"),
        "blocked": decision.blocked,
        "severity": decision.severity,
        "tags": decision.tags,
        "timestamp": _utc_timestamp(),
    }
    if preview:
        audit["commandPreview"] = preview
    decision.payload.setdefault("preToolUseAudit", audit)

    # Map to HandlerResult for dispatcher
    hr = HandlerResult()
    hr.decision_payload = decision.to_dict()
    hr.continue_value = not decision.blocked
    # Audio policy: mute for clean allow
    perm = decision.payload.get("permissionDecision")
    if perm == "allow" and not decision.blocked:
        hr.suppress_audio = True
    else:
        hr.audio_type = PRE_TOOL_USE
    return hr


def main() -> int:  # pragma: no cover - simple CLI passthrough
    parser = argparse.ArgumentParser(description="Claude Code PreToolUse (function)" )
    parser.add_argument("--enable-audio", action="store_true")
    _ = parser.parse_args()
    try:
        # Minimal CLI: read stdin JSON and evaluate using handler; emit continue only
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
    except Exception:
        payload = {}
    from herald import build_default_dispatcher
    disp = build_default_dispatcher()
    report = disp.dispatch(PRE_TOOL_USE, payload=payload)
    print(json.dumps(report.response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
