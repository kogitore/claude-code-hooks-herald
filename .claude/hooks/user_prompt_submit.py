#!/usr/bin/env python3
"""UserPromptSubmit hook — minimal but preserves existing test expectations.

Kept:
- prompt extraction + truncation
- suspicious pattern scan
- simple rate limiting (per user/session)
- issue aggregation → block + reason
- audio only when issues present

Removed: bloated narrative docstring, dataclass, redundant layering.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from utils.constants import USER_PROMPT_SUBMIT
from utils.handler_result import HandlerResult


PROMPT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "prompt_submissions.jsonl"
RATE_LIMIT_PATH = Path(__file__).resolve().parents[2] / "logs" / "prompt_rates.json"
MAX_PROMPT_LENGTH = 4000
MAX_PREVIEW = 240
RATE_LIMIT_SECONDS = 1.0

SUSPICIOUS_PATTERNS = [
    (re.compile(r"rm\s+-rf\s+", re.IGNORECASE), "dangerous_command"),
    (re.compile(r"drop\s+table", re.IGNORECASE), "sql_drop"),
    (re.compile(r"(https?://)?(?:[\w-]+\.){1,}onion", re.IGNORECASE), "tor_link"),
]


def _process_prompt(context: Dict[str, Any]) -> Tuple[Dict[str, Any], Tuple[str, ...], Optional[str], bool]:
    prompt, issues = _extract_prompt(context)
    metadata = context.get("metadata") if isinstance(context.get("metadata"), dict) else {}
    user_id = context.get("user_id") or context.get("userId")
    session_id = context.get("session_id") or context.get("sessionId")
    timestamp = context.get("timestamp") if isinstance(context.get("timestamp"), str) else _utc_timestamp()

    rate_issue = _check_rate_limit(user_id, session_id)
    if rate_issue:
        issues += (rate_issue,)
    suspicious = _scan_prompt(prompt)
    issues += suspicious

    truncated = False
    sanitized = prompt.strip()
    if len(sanitized) > MAX_PROMPT_LENGTH:
        sanitized = sanitized[:MAX_PROMPT_LENGTH]
        truncated = True
        issues += ("prompt_truncated",)

    should_alert = bool(issues)
    payload = {
        "userPrompt": {
            "prompt": sanitized,
            "truncated": truncated,
            "length": len(sanitized),
            "timestamp": timestamp,
        }
    }
    if user_id:
        payload["userPrompt"]["userId"] = str(user_id)
    if session_id:
        payload["userPrompt"]["sessionId"] = str(session_id)
    if metadata:
        payload["userPrompt"]["metadata"] = metadata
    if issues:
        payload["userPrompt"]["issues"] = list(dict.fromkeys(issues))
    if should_alert:
        payload["userPrompt"]["requiresAttention"] = True

    preview = sanitized[:MAX_PREVIEW] if sanitized else None

    _record_submission(
        {
            "timestamp": timestamp,
            "userId": user_id,
            "sessionId": session_id,
            "length": len(sanitized),
            "issues": list(dict.fromkeys(issues)),
        }
    )
    return payload, issues, preview, should_alert


def _extract_prompt(context: Dict[str, Any]) -> Tuple[str, Tuple[str, ...]]:
    prompt = context.get("prompt")
    if isinstance(prompt, str):
        cleaned = prompt.replace("\r\n", "\n")
        return cleaned, tuple()
    return "", ("missing_prompt",)


def _scan_prompt(prompt: str) -> Tuple[str, ...]:
    findings = []
    lowered = prompt.lower()
    if not lowered.strip():
        findings.append("empty_prompt")
    for pattern, tag in SUSPICIOUS_PATTERNS:
        if pattern.search(prompt):
            findings.append(tag)
    if prompt.count("\n") > 100:
        findings.append("excessive_newlines")
    return tuple(dict.fromkeys(findings))


def _check_rate_limit(user_id: Any, session_id: Any) -> Optional[str]:
    ref = str(user_id or session_id or "global")
    now = time.time()
    data = _read_rate_tracker()
    last = data.get(ref)
    data[ref] = now
    _write_rate_tracker(data)
    if isinstance(last, (int, float)) and now - float(last) < RATE_LIMIT_SECONDS:
        return "rate_limited"
    return None


def _read_rate_tracker() -> Dict[str, float]:
    if not RATE_LIMIT_PATH.exists():
        return {}
    try:
        content = json.loads(RATE_LIMIT_PATH.read_text(encoding="utf-8"))
        if isinstance(content, dict):
            return {str(k): float(v) for k, v in content.items() if isinstance(v, (int, float))}
    except Exception:
        pass
    return {}


def _write_rate_tracker(data: Dict[str, float]) -> None:
    try:
        RATE_LIMIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RATE_LIMIT_PATH.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception:
        pass


def _record_submission(record: Dict[str, Any]) -> None:
    try:
        PROMPT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record["recordedAt"] = _utc_timestamp()
        with PROMPT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")
    except OSError:
        pass


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Function-based simple handler for dispatcher ---------------------------
def handle_user_prompt_submit(context) -> "HandlerResult":  # type: ignore[name-defined]
    payload: Dict[str, Any] = context.payload if isinstance(context.payload, dict) else {}
    processed_payload, issues, preview, should_alert = _process_prompt(payload)
    base = processed_payload.get("userPrompt", {})
    ctx = {
        "promptPreview": preview,
        "issues": list(issues),
        "timestamp": _utc_timestamp(),
        **{k: v for k, v in base.items() if k not in {"issues", "requiresAttention"}},
    }
    hr = HandlerResult()
    hr.decision_payload = {"additionalContext": ctx}
    if issues:
        hr.decision_payload["decision"] = "block"
        hr.decision_payload["reason"] = "Issues detected: " + ", ".join(i.replace("_", " ") for i in issues)
        hr.continue_value = False
    else:
        hr.continue_value = True
    if should_alert:
        hr.audio_type = USER_PROMPT_SUBMIT
    else:
        hr.suppress_audio = True
    return hr


def main() -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Claude Code UserPromptSubmit (function)")
    parser.add_argument("--enable-audio", action="store_true")
    _ = parser.parse_args()
    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
    except Exception:
        payload = {}
    from herald import dispatch
    response = dispatch(USER_PROMPT_SUBMIT, payload=payload, enable_audio=False)
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
