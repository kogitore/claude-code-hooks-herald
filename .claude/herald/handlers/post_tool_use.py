#!/usr/bin/env python3
"""PostToolUse hook - simplified audit and alerting."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from herald.utils.constants import POST_TOOL_USE
from herald.utils.decision_api import DecisionAPI, DecisionResult
from herald.utils.handler_result import HandlerResult


MAX_OUTPUT_SNIPPET = 600
AUDIT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "tool_audit.jsonl"


def _extract_tool_name(payload: dict[str, object]) -> str:
    """Extract tool name from various possible keys."""
    for key in ("tool", "toolName", "tool_name", "name"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return "unknown"


def _extract_exit_code(result: dict[str, object]) -> int | None:
    """Extract exit code from result, handling various types."""
    ec = result.get("exitCode") or result.get("exit_code")
    if isinstance(ec, int):
        return ec
    if isinstance(ec, str):
        try:
            return int(ec)
        except ValueError:
            return None
    return None


def _extract_error_message(result: dict[str, object]) -> str | None:
    """Extract error message from various possible keys."""
    for key in ("toolError", "error", "stderr", "traceback"):
        v = result.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _detect_success(result: dict[str, object], exit_code: int | None) -> bool:
    """Determine if tool execution was successful."""
    s = result.get("success")
    if isinstance(s, bool):
        return s
    if exit_code is not None:
        return exit_code == 0
    status = result.get("status")
    return isinstance(status, str) and status.lower() in {"ok", "success", "completed"}


def _sanitize_result(result: dict[str, object]) -> dict[str, object]:
    """Sanitize result for audit logging, redacting sensitive data."""
    out: dict[str, object] = {}
    if "success" in result:
        out["success"] = bool(result.get("success"))

    outp = result.get("output")
    if isinstance(outp, str) and outp:
        s = outp.strip()
        out["outputPreview"] = s[:MAX_OUTPUT_SNIPPET]
        out["outputTruncated"] = len(s) > MAX_OUTPUT_SNIPPET

    err = _extract_error_message(result)
    if err:
        out["errorMessage"] = err[:MAX_OUTPUT_SNIPPET]

    ec = _extract_exit_code(result)
    if ec is not None:
        out["exitCode"] = ec

    # Redact potentially large outputs
    for k in ("stdout", "stderr"):
        if k in result:
            out[k] = "<redacted>"

    return out


def _utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _append_audit(record: dict[str, object]) -> None:
    """Append audit record to log file."""
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
    except OSError:
        pass


def handle_post_tool_use(context) -> HandlerResult:
    """Handle post tool use event - audit and alert on failures."""
    payload: dict[str, object] = context.payload if isinstance(context.payload, dict) else {}
    api: DecisionAPI = context.decision_api or DecisionAPI()

    tool = _extract_tool_name(payload)
    result_raw = payload.get("result")
    result: dict[str, object] = result_raw if isinstance(result_raw, dict) else {}

    ec = _extract_exit_code(result)
    success = _detect_success(result, ec)
    err = _extract_error_message(result)

    # Make decision using DecisionAPI
    decision = api.post_tool_use_decision(tool, result)

    # Determine if we should alert (play audio)
    should_alert = (not success) or bool(err) or decision.blocked

    # Sanitize result for audit
    sanitized = _sanitize_result(result)

    # Add alert flags
    alerts_list: list[str] = []
    existing_alerts = sanitized.get("alerts")
    if isinstance(existing_alerts, list):
        alerts_list = existing_alerts

    if decision.blocked:
        alerts_list.append("decision_blocked")

    if err:
        alerts_list.append("error_detected")

    if not success and "error_detected" not in alerts_list:
        alerts_list.append("execution_failed")

    if alerts_list:
        sanitized["alerts"] = alerts_list

    # Build audit record
    audit: dict[str, object] = {
        "tool": tool,
        "timestamp": _utc_timestamp(),
        "result": sanitized,
    }
    if ec is not None:
        audit["exitCode"] = ec
    if err:
        audit["errorMessage"] = err

    # Update decision payload with audit context
    decision.payload["additionalContext"] = audit

    # Append to audit log
    _append_audit({**audit, "decision": "block" if decision.blocked else "allow"})

    # Build handler result
    hr = HandlerResult()
    hr.decision_payload = decision.to_dict()
    hr.continue_value = not decision.blocked

    if should_alert:
        hr.audio_type = POST_TOOL_USE
    else:
        hr.suppress_audio = True

    return hr


def main() -> int:
    """Entry point for manual invocations."""
    parser = argparse.ArgumentParser(description="Claude Code PostToolUse hook")
    parser.add_argument("--enable-audio", action="store_true",
                       help="Enable audio feedback")
    _ = parser.parse_args()

    try:
        payload = json.loads(sys.stdin.read().strip() or "{}")
    except Exception:
        payload = {}

    from herald.dispatcher import dispatch
    response = dispatch(POST_TOOL_USE, payload=payload)
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
