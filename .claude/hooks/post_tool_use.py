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

from utils.base_hook import BaseHook, HookExecutionResult
from utils.common_io import parse_stdin
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


class PostToolUseHook(BaseHook):
    """PostToolUse hook for tool execution result processing."""

    default_audio_event = POST_TOOL_USE
    default_throttle_seconds = 45

    def __init__(
        self,
        *,
        decision_api: Optional[DecisionAPI] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._decision_api = decision_api or DecisionAPI()
        self._last_decision: Optional[DecisionResponse] = None
        self._should_alert: bool = False

    # -- BaseHook overrides ---------------------------------------------
    def validate_input(self, data: Dict[str, Any]) -> bool:  # type: ignore[override]
        return isinstance(data, dict)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[override]
        """Legacy compatibility path (unused)."""
        return {}

    def handle_error(self, error: Exception) -> Dict[str, Any]:  # type: ignore[override]
        fallback = self._decision_api.block(
            "工具結果處理失敗，已阻擋後續流程",
            event=POST_TOOL_USE,
            additional_context={"error": type(error).__name__},
            severity="high",
            tags=["posttooluse:exception"],
        )
        self._last_decision = fallback
        self._should_alert = True
        return fallback.to_dict()

    def _attach_audio(  # type: ignore[override]
        self,
        result: HookExecutionResult,
        audio_event: str,
        *,
        enable_audio: bool,
        throttle_key: Optional[str],
        throttle_seconds: Optional[int],
    ) -> None:
        if not self._should_alert:
            return
        super()._attach_audio(
            result,
            audio_event,
            enable_audio=enable_audio,
            throttle_key=throttle_key,
            throttle_seconds=throttle_seconds,
        )

    # -- Custom behaviour -----------------------------------------------
    def handle_hook_logic(
        self,
        context: Dict[str, Any],
        *,
        parsed_args: Optional[argparse.Namespace] = None,
    ) -> HookExecutionResult:
        processed = self._evaluate_context(context)
        self._last_decision = processed.decision
        self._should_alert = processed.should_alert

        audit_record = {
            "tool": processed.tool,
            "timestamp": _utc_timestamp(),
            "exitCode": processed.exit_code,
            "duration": processed.duration,
            "result": processed.sanitized_result,
            "shouldAlert": processed.should_alert,
        }
        if processed.error_message:
            audit_record["errorMessage"] = processed.error_message

        additional_context = json.dumps(audit_record, ensure_ascii=False)

        result = HookExecutionResult()
        result.payload["hookSpecificOutput"] = {
            "hookEventName": POST_TOOL_USE,
            "additionalContext": additional_context,
        }

        if processed.decision.blocked:
            reason = processed.decision.payload.get("reason") or processed.error_message or "PostToolUse blocked by policy"
            result.payload["decision"] = "block"
            result.payload["reason"] = reason
            result.continue_value = False

        _append_audit_record({**audit_record, "decision": "block" if processed.decision.blocked else "allow"})

        if processed.should_alert:
            result.notes.append("post_tool_use_alert")
        return result

    def _evaluate_context(self, context: Dict[str, Any]) -> PostToolUseProcessing:
        tool = _extract_tool_name(context)
        result_section = context.get("result") if isinstance(context.get("result"), dict) else {}
        if not isinstance(result_section, dict):
            result_section = {}

        exit_code = _extract_exit_code(result_section)
        success = _detect_success(result_section, exit_code)
        duration = _extract_duration(context)
        error_message = _extract_error_message(result_section)

        decision = self._decision_api.post_tool_use_decision(tool, result_section)

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

    # Append audit record to decision payload and set hookSpecificOutput for compatibility
    extra_ctx = {k: v for k, v in audit_record.items() if v is not None}
    decision.payload["additionalContext"] = extra_ctx
    decision.payload["hookSpecificOutput"] = {
        "hookEventName": POST_TOOL_USE,
        "additionalContext": json.dumps(extra_ctx, ensure_ascii=False),
    }

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


def main() -> int:
    """CLI entry point for PostToolUse hook."""

    parser = argparse.ArgumentParser(description="Claude Code PostToolUse hook")
    parser.add_argument("--enable-audio", action="store_true", help="Enable actual audio playback")
    parser.add_argument("--json-only", action="store_true", help="Reserved for compatibility; no-op")
    args = parser.parse_args()

    payload, _ = parse_stdin()
    hook = PostToolUseHook()

    result = hook.execute(payload, enable_audio=bool(args.enable_audio), parsed_args=args)

    decision = hook._last_decision  # internal use for logging
    if decision:
        decision_value = decision.payload.get("permissionDecision") or decision.payload.get("decision")
        log_parts = [
            "[PostToolUse]",
            f"tool={payload.get('tool', 'unknown')}",
            f"decision={decision_value}",
            f"blocked={decision.blocked}",
        ]
        if decision.severity:
            log_parts.append(f"severity={decision.severity}")
        if decision.tags:
            log_parts.append(f"tags={','.join(decision.tags)}")
        try:
            print(" ".join(log_parts), file=sys.stderr)
        except OSError:
            pass

    hook.emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
