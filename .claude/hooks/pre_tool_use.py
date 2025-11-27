#!/usr/bin/env python3
"""PreToolUse hook - simplified security evaluation."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from utils.decision_api import DecisionAPI, DecisionResult
from utils.constants import PRE_TOOL_USE, MAX_COMMAND_PREVIEW
from utils.handler_result import HandlerResult

# Module-level logger
_log = logging.getLogger("hooks.pre_tool_use")
if not _log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    _log.addHandler(_handler)
    _log.setLevel(logging.WARNING)


def _preview_command(payload: dict[str, object]) -> str | None:
    """Extract command preview from payload."""
    cmd = payload.get("command")
    if isinstance(cmd, str) and cmd.strip():
        return cmd.strip()[:MAX_COMMAND_PREVIEW]
    args = payload.get("args")
    if isinstance(args, list) and args:
        joined = " ".join(str(a) for a in args)
        return joined[:MAX_COMMAND_PREVIEW] if joined else None
    return None


def _utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def handle_pre_tool_use(context) -> HandlerResult:
    """Handle pre tool use event - security evaluation before execution."""
    payload: dict[str, object] = context.payload if isinstance(context.payload, dict) else {}
    api: DecisionAPI = context.decision_api or DecisionAPI()

    issues: list[str] = []

    # Extract tool name
    tool_raw = (
        payload.get("tool")
        or payload.get("toolName")
        or payload.get("tool_name")
        or payload.get("name")
        or "unknown"
    )
    tool = str(tool_raw) if tool_raw else "unknown"
    if not tool or not tool.strip():
        tool = "unknown"
        issues.append("missing_tool_name")

    # Extract and parse tool input
    raw = payload.get("toolInput") or payload.get("tool_input") or payload.get("input")
    tool_input: dict[str, object] | None = None
    preview: str | None = None

    if isinstance(raw, dict):
        tool_input, preview = raw, _preview_command(raw)
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                tool_input, preview = parsed, _preview_command(parsed)
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

    # Make security decision
    try:
        # Provide empty dict if tool_input is None
        decision = api.pre_tool_use_decision(tool, tool_input or {})
    except Exception as exc:
        # Fallback to ask decision on API failure
        # Note: issues list will be added to additionalContext later
        decision = DecisionResult(
            "ask",
            "無法評估工具安全性，請人工確認",
            blocked=True,
        )
        # Store error info for later
        issues.append(f"api_error:{type(exc).__name__}")

    # If there are parsing issues, escalate to ask
    if not decision.blocked and issues:
        decision = DecisionResult(
            "ask",
            "工具輸入格式不明確，請人工確認",
            blocked=True,
        )

    # Build additional context - always start fresh and merge
    existing_context = decision.payload.get("additionalContext")
    additional_context: dict[str, object] = {}

    # Merge existing context if present
    if isinstance(existing_context, dict) and existing_context:
        additional_context.update(existing_context)

    # Always set tool and issues
    additional_context["tool"] = tool
    if issues:
        additional_context["issues"] = issues

    # Build audit record
    audit: dict[str, object] = {
        "decision": decision.payload.get("permissionDecision") or decision.payload.get("decision", "unknown"),
        "blocked": decision.blocked,
        "timestamp": _utc_timestamp(),
    }
    if preview:
        audit["commandPreview"] = preview

    additional_context["preToolUseAudit"] = audit

    # Update decision payload
    decision.payload["additionalContext"] = additional_context

    # Build handler result
    hr = HandlerResult()
    hr.decision_payload = decision.to_dict()
    hr.continue_value = not decision.blocked

    perm = decision.payload.get("permissionDecision")
    if perm == "allow" and not decision.blocked:
        hr.suppress_audio = True
    else:
        hr.audio_type = PRE_TOOL_USE

    return hr


def main() -> int:
    """Entry point for manual invocations."""
    parser = argparse.ArgumentParser(description="Claude Code PreToolUse hook")
    parser.add_argument("--enable-audio", action="store_true",
                       help="Enable audio feedback")
    _ = parser.parse_args()

    try:
        payload = json.loads(sys.stdin.read().strip() or "{}")
    except Exception:
        payload = {}

    from herald import dispatch  # pyright: ignore[reportImplicitRelativeImport]
    response = dispatch(PRE_TOOL_USE, payload)
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
