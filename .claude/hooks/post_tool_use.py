#!/usr/bin/env python3
"""PostToolUse hook — compact audit and decision mapping."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from utils.constants import POST_TOOL_USE
from utils.decision_api import DecisionAPI


MAX_OUTPUT_SNIPPET = 600
AUDIT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "tool_audit.jsonl"


def _extract_tool_name(payload: Dict[str, Any]) -> str:
    for key in ("tool", "toolName", "tool_name", "name"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return "unknown"


def _extract_exit_code(result: Dict[str, Any]) -> Optional[int]:
    ec = result.get("exitCode") or result.get("exit_code")
    if isinstance(ec, int):
        return ec
    if isinstance(ec, str):
        try:
            return int(ec)
        except ValueError:
            return None
    return None


def _extract_error_message(result: Dict[str, Any]) -> Optional[str]:
    for key in ("toolError", "error", "stderr", "traceback"):
        v = result.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _detect_success(result: Dict[str, Any], exit_code: Optional[int]) -> bool:
    s = result.get("success")
    if isinstance(s, bool):
        return s
    if exit_code is not None:
        return exit_code == 0
    status = result.get("status")
    return isinstance(status, str) and status.lower() in {"ok", "success", "completed"}


def _sanitize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
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
    for k in ("stdout", "stderr"):
        if k in result:
            out[k] = "<redacted>"
    return out


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(record: Dict[str, Any]) -> None:
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def handle_post_tool_use(context) -> "HandlerResult":  # type: ignore[name-defined]
    from herald import HandlerResult

    payload: Dict[str, Any] = context.payload if isinstance(context.payload, dict) else {}
    api: DecisionAPI = context.decision_api or DecisionAPI()

    tool = _extract_tool_name(payload)
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    if not isinstance(result, dict):
        result = {}

    ec = _extract_exit_code(result)
    success = _detect_success(result, ec)
    err = _extract_error_message(result)

    decision = api.post_tool_use_decision(tool, result)

    should_alert = (not success) or bool(err) or decision.blocked
    sanitized = _sanitize_result(result)
    if decision.blocked:
        sanitized.setdefault("alerts", []).append("decision_blocked")
    if err:
        sanitized.setdefault("alerts", []).append("error_detected")
    if not success and "error_detected" not in sanitized.get("alerts", []):
        sanitized.setdefault("alerts", []).append("execution_failed")

    audit = {
        "tool": tool,
        "timestamp": _utc_timestamp(),
        "result": sanitized,
    }
    if ec is not None:
        audit["exitCode"] = ec
    if err:
        audit["errorMessage"] = err

    decision.payload["additionalContext"] = audit
    _append_audit({**audit, "decision": "block" if decision.blocked else "allow"})

    hr = HandlerResult()
    hr.decision_payload = decision.to_dict()
    hr.continue_value = not decision.blocked
    if should_alert:
        hr.audio_type = POST_TOOL_USE
    else:
        hr.suppress_audio = True
    return hr


def main() -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Claude Code PostToolUse (KISS)")
    parser.add_argument("--enable-audio", action="store_true")
    _ = parser.parse_args()
    try:
        payload = json.loads(sys.stdin.read().strip() or "{}")
    except Exception:
        payload = {}
    from herald import build_default_dispatcher
    report = build_default_dispatcher().dispatch(POST_TOOL_USE, payload=payload)
    print(json.dumps(report.response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
