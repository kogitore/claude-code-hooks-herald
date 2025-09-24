#!/usr/bin/env python3
"""PreToolUse hook — KISS edition.

Single responsibility: read JSON, evaluate via DecisionAPI, emit contract JSON.
Audio: only for ask/deny/block; clean allows are silent.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.decision_api import DecisionAPI
from utils.constants import PRE_TOOL_USE


MAX_COMMAND_PREVIEW = 240


def _preview_command(payload: Dict[str, Any]) -> Optional[str]:
    cmd = payload.get("command")
    if isinstance(cmd, str) and cmd.strip():
        return cmd.strip()[:MAX_COMMAND_PREVIEW]
    args = payload.get("args")
    if isinstance(args, list) and args:
        joined = " ".join(str(a) for a in args)
        return joined[:MAX_COMMAND_PREVIEW] if joined else None
    return None


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def handle_pre_tool_use(context) -> "HandlerResult":  # type: ignore[name-defined]
    from herald import HandlerResult  # local import to avoid circulars

    payload: Dict[str, Any] = context.payload if isinstance(context.payload, dict) else {}
    api: DecisionAPI = context.decision_api or DecisionAPI()

    issues: List[str] = []

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

    raw = payload.get("toolInput") or payload.get("tool_input") or payload.get("input")
    tool_input: Optional[Dict[str, Any]] = None
    preview: Optional[str] = None
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

    try:
        decision = api.pre_tool_use_decision(tool, tool_input)
    except Exception as exc:
        decision = api.ask(
            "無法評估工具安全性，請人工確認",
            event=PRE_TOOL_USE,
            additional_context={"tool": tool, "error": type(exc).__name__},
        )

    if not decision.blocked and issues:
        decision = api.ask(
            "工具輸入格式不明確，請人工確認",
            event=PRE_TOOL_USE,
            additional_context={"tool": tool, "issues": issues},
        )

    extra = decision.payload.setdefault("additionalContext", {})
    extra.setdefault("tool", tool)
    if issues:
        extra.setdefault("issues", issues)
    audit = {
        "decision": decision.payload.get("permissionDecision") or decision.payload.get("decision", "unknown"),
        "blocked": decision.blocked,
        "timestamp": _utc_timestamp(),
    }
    if preview:
        audit["commandPreview"] = preview
    decision.payload.setdefault("preToolUseAudit", audit)

    hr = HandlerResult()
    hr.decision_payload = decision.to_dict()
    hr.continue_value = not decision.blocked
    perm = decision.payload.get("permissionDecision")
    if perm == "allow" and not decision.blocked:
        hr.suppress_audio = True
    else:
        hr.audio_type = PRE_TOOL_USE
    return hr


def main() -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Claude Code PreToolUse (KISS)")
    parser.add_argument("--enable-audio", action="store_true")
    _ = parser.parse_args()
    try:
        payload = json.loads(sys.stdin.read().strip() or "{}")
    except Exception:
        payload = {}
    from herald import build_default_dispatcher
    report = build_default_dispatcher().dispatch(PRE_TOOL_USE, payload=payload)
    print(json.dumps(report.response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
