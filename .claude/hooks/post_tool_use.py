#!/usr/bin/env python3
"""PostToolUse hook for tool execution result processing and audit.

This hook is triggered AFTER a tool has been executed and can implement:
- Result validation and filtering
- Security audit logging
- Result transformation
- Error handling and recovery

IMPLEMENTATION REQUIREMENTS for Codex:
1. Inherit from BaseHook with default_audio_event = "PostToolUse"
2. Implement handle_hook_logic() method that:
   - Extracts tool execution results from context
   - Processes/validates the results
   - Applies any post-execution policies
   - Returns HookExecutionResult with continue/modified response
3. Handle tool execution states:
   - Successful tool execution with results
   - Tool execution errors/failures
   - Timeout or interrupted executions
4. Audio integration:
   - Play audio for significant events (errors, security violations)
   - Different audio cues for success vs. failure scenarios

CONTEXT FORMAT:
{
    "tool": "bash|read|write|...",
    "toolInput": {...},  // Original tool parameters
    "result": {
        "success": true|false,
        "output": "...",     // Tool output
        "error": "...",      // Error message if failed
        "exit_code": 0,      // For bash tools
        ...
    },
    "execution_time": 1.23,  // Seconds
    "metadata": {...}
}

CRITICAL NOTES:
- Focus on audit and monitoring, not blocking (unlike PreToolUse)
- Should capture security-relevant events for logging
- Can modify results but should preserve original data
- Consider rate limiting for frequent tool executions
- Log high-risk tool combinations or patterns
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from utils.constants import POST_TOOL_USE
from utils.decision_api import DecisionAPI, DecisionResponse


MAX_OUTPUT_SNIPPET = 600
AUDIT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "tool_audit.jsonl"


@dataclass
class PostToolUseProcessing:
    decision: DecisionResponse
    sanitized_result: Dict[str, Any]
    should_alert: bool
    tool: str
    exit_code: Optional[int]
    duration: Optional[float]
    error_message: Optional[str]


def _evaluate_context(context: Dict[str, Any], api: DecisionAPI) -> PostToolUseProcessing:
    tool = _extract_tool_name(context)
    result_section = context.get("result") if isinstance(context.get("result"), dict) else {}
    if not isinstance(result_section, dict):
        result_section = {}

    exit_code = _extract_exit_code(result_section)
    success = _detect_success(result_section, exit_code)
    duration = _extract_duration(context)
    error_message = _extract_error_message(result_section)

    decision = api.post_tool_use_decision(tool, result_section)

    should_alert = not success or bool(error_message) or decision.blocked

    sanitized = _sanitize_result_for_output(result_section)

    if decision.blocked:
        sanitized.setdefault("alerts", []).append("decision_blocked")
    if error_message:
        sanitized.setdefault("alerts", []).append("error_detected")
    if not success and "error_detected" not in sanitized.get("alerts", []):
        sanitized.setdefault("alerts", []).append("execution_failed")

    return PostToolUseProcessing(
        decision=decision,
        sanitized_result=sanitized,
        should_alert=should_alert,
        tool=tool,
        exit_code=exit_code,
        duration=duration,
        error_message=error_message,
    )


def _sanitize_result_for_output(result_section: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    if "success" in result_section:
        sanitized["success"] = bool(result_section.get("success"))
    output = result_section.get("output")
    if isinstance(output, str) and output:
        snippet = output.strip()
        if len(snippet) > MAX_OUTPUT_SNIPPET:
            sanitized["outputPreview"] = snippet[:MAX_OUTPUT_SNIPPET]
            sanitized["outputTruncated"] = True
        else:
            sanitized["outputPreview"] = snippet
    error = _extract_error_message(result_section)
    if error:
        sanitized["errorMessage"] = error[:MAX_OUTPUT_SNIPPET]
    exit_code = _extract_exit_code(result_section)
    if exit_code is not None:
        sanitized["exitCode"] = exit_code
    for key in ("stdout", "stderr"):
        if key in result_section:
            sanitized[key] = "<redacted>"
    return sanitized


def _extract_tool_name(payload: Dict[str, Any]) -> str:
    # 支援Claude Code標準欄位名稱
    for key in ("tool", "toolName", "tool_name", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def _extract_exit_code(result_section: Dict[str, Any]) -> Optional[int]:
    exit_code = result_section.get("exitCode") or result_section.get("exit_code")
    if isinstance(exit_code, int):
        return exit_code
    if isinstance(exit_code, str):
        try:
            return int(exit_code)
        except ValueError:
            return None
    return None


def _detect_success(result_section: Dict[str, Any], exit_code: Optional[int]) -> bool:
    success = result_section.get("success")
    if isinstance(success, bool):
        return success
    if exit_code is not None:
        return exit_code == 0
    status = result_section.get("status")
    if isinstance(status, str):
        return status.lower() in {"ok", "success", "completed"}
    return True


def _extract_duration(context: Dict[str, Any]) -> Optional[float]:
    duration = context.get("execution_time") or context.get("duration")
    if isinstance(duration, (int, float)):
        return float(duration)
    if isinstance(duration, str):
        try:
            return float(duration)
        except ValueError:
            return None
    return None


def _extract_error_message(result_section: Dict[str, Any]) -> Optional[str]:
    for key in ("toolError", "error", "stderr", "traceback"):
        value = result_section.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _append_audit_record(record: Dict[str, Any]) -> None:
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Function-based simple handler for dispatcher ---------------------------
def handle_post_tool_use(context) -> "HandlerResult":  # type: ignore[name-defined]
    """Function handler mirroring PostToolUseHook behaviour in simplified form.

    - Extract tool, result, duration/error fields
    - Evaluate decision via DecisionAPI
    - Build sanitized audit payload for additionalContext
    - Suppress audio unless should_alert or blocked
    """
    from herald import HandlerResult  # local import

    payload: Dict[str, Any] = context.payload if isinstance(context.payload, dict) else {}
    api: DecisionAPI = context.decision_api or DecisionAPI()

    tool = _extract_tool_name(payload)
    result_section = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    if not isinstance(result_section, dict):
        result_section = {}

    exit_code = _extract_exit_code(result_section)
    success = _detect_success(result_section, exit_code)
    duration = _extract_duration(payload)
    error_message = _extract_error_message(result_section)

    decision = api.post_tool_use_decision(tool, result_section)

    should_alert = (not success) or bool(error_message) or decision.blocked

    sanitized = _sanitize_result_for_output(result_section)
    if decision.blocked:
        sanitized.setdefault("alerts", []).append("decision_blocked")
    if error_message:
        sanitized.setdefault("alerts", []).append("error_detected")
    if not success and "error_detected" not in sanitized.get("alerts", []):
        sanitized.setdefault("alerts", []).append("execution_failed")

    audit_record = {
        "tool": tool,
        "timestamp": _utc_timestamp(),
        "exitCode": exit_code,
        "duration": duration,
        "result": sanitized,
        "shouldAlert": should_alert,
    }
    if error_message:
        audit_record["errorMessage"] = error_message

    # Provide a minimal decision payload for dispatcher mapping
    decision.payload["additionalContext"] = {k: v for k, v in audit_record.items() if v is not None}

    # Persist audit line
    _append_audit_record({**audit_record, "decision": "block" if decision.blocked else "allow"})

    hr = HandlerResult()
    hr.decision_payload = decision.to_dict()
    hr.continue_value = not decision.blocked
    if should_alert:
        hr.audio_type = POST_TOOL_USE
    else:
        hr.suppress_audio = True
    return hr


def main() -> int:  # pragma: no cover - simple CLI passthrough
    parser = argparse.ArgumentParser(description="Claude Code PostToolUse (function)")
    parser.add_argument("--enable-audio", action="store_true")
    _ = parser.parse_args()
    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
    except Exception:
        payload = {}
    from herald import build_default_dispatcher
    disp = build_default_dispatcher()
    report = disp.dispatch(POST_TOOL_USE, payload=payload)
    print(json.dumps(report.response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
