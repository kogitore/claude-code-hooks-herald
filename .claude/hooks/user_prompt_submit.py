#!/usr/bin/env python3
"""UserPromptSubmit hook for user interaction processing and validation.

This hook is triggered when a user submits a prompt and can implement:
- Prompt validation and sanitization
- User input logging and audit
- Prompt preprocessing and enhancement
- Rate limiting and abuse prevention

IMPLEMENTATION REQUIREMENTS for Codex:
1. Inherit from BaseHook with default_audio_event = "UserPromptSubmit"
2. Implement handle_hook_logic() method that:
   - Extracts user prompt from context
   - Validates and processes prompt content
   - Applies user input policies
   - Returns HookExecutionResult with processed prompt
3. Handle prompt processing:
   - Content validation and sanitization
   - Length and complexity limits
   - Abuse pattern detection
   - User session rate limiting
4. Audio integration:
   - Feedback for prompt submission
   - Different cues for validation failures
   - Throttled to avoid audio spam

CONTEXT FORMAT:
{
    "prompt": "User's input text...",
    "user_id": "uuid-string",
    "session_id": "uuid-string",
    "timestamp": "2025-01-01T00:00:00Z",
    "metadata": {
        "length": 1234,
        "language": "en",
        "source": "cli|web|api"
    }
}

CRITICAL NOTES:
- Handle user privacy and data protection carefully
- Implement prompt sanitization to prevent injection attacks
- Consider rate limiting to prevent abuse
- Log user interactions for audit but respect privacy
- Should be fast to avoid user experience impact
- Consider multilingual prompt processing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from utils.base_hook import BaseHook, HookExecutionResult
from utils.common_io import parse_stdin
from utils.constants import USER_PROMPT_SUBMIT


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


@dataclass
class PromptProcessingResult:
    payload: Dict[str, Any]
    should_alert: bool
    issues: Tuple[str, ...]
    prompt_preview: Optional[str]


class UserPromptSubmitHook(BaseHook):
    """UserPromptSubmit hook for user input processing and validation."""

    default_audio_event = USER_PROMPT_SUBMIT
    default_throttle_seconds = 10

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._should_alert = False
        self._issues: Tuple[str, ...] = ()
        self._preview: Optional[str] = None

    # -- BaseHook overrides ---------------------------------------------
    def validate_input(self, data: Dict[str, Any]) -> bool:  # type: ignore[override]
        return isinstance(data, dict)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[override]
        """Legacy compatibility path (unused)."""
        return {}

    def handle_error(self, error: Exception) -> Dict[str, Any]:  # type: ignore[override]
        self._should_alert = True
        self._issues = ("prompt_handler_exception",)
        return {
            "userPrompt": {
                "status": "error",
                "reason": type(error).__name__,
            }
        }

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
        processed = self._process_prompt(context)
        self._should_alert = processed.should_alert
        self._issues = processed.issues
        self._preview = processed.prompt_preview

        context_payload = {
            "promptPreview": processed.prompt_preview,
            "issues": list(processed.issues),
            "timestamp": _utc_timestamp(),
        }
        payload_data = processed.payload.get('userPrompt', {}) if isinstance(processed.payload, dict) else {}
        context_payload.update({k: v for k, v in payload_data.items() if k not in {"issues", "requiresAttention"}})

        result = HookExecutionResult()
        result.payload["hookSpecificOutput"] = {
            "hookEventName": USER_PROMPT_SUBMIT,
            "additionalContext": json.dumps(context_payload, ensure_ascii=False),
        }

        if processed.issues:
            readable = ", ".join(issue.replace("_", " ") for issue in processed.issues)
            reason = f"Issues detected: {readable}"
            result.payload["decision"] = "block"
            result.payload["reason"] = reason
            result.continue_value = False

        if processed.should_alert:
            result.notes.append("user_prompt_alert")
        return result

    def _process_prompt(self, context: Dict[str, Any]) -> PromptProcessingResult:
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
        sanitized_prompt = prompt.strip()
        if len(sanitized_prompt) > MAX_PROMPT_LENGTH:
            sanitized_prompt = sanitized_prompt[:MAX_PROMPT_LENGTH]
            truncated = True
            issues += ("prompt_truncated",)

        should_alert = bool(issues)

        payload = {
            "userPrompt": {
                "prompt": sanitized_prompt,
                "truncated": truncated,
                "length": len(sanitized_prompt),
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

        preview = sanitized_prompt[:MAX_PREVIEW] if sanitized_prompt else None

        _record_submission(
            {
                "timestamp": timestamp,
                "userId": user_id,
                "sessionId": session_id,
                "length": len(sanitized_prompt),
                "issues": list(dict.fromkeys(issues)),
            }
        )

        return PromptProcessingResult(
            payload=payload,
            should_alert=should_alert,
            issues=issues,
            prompt_preview=preview,
        )

    @property
    def issues(self) -> Tuple[str, ...]:
        return self._issues

    @property
    def preview(self) -> Optional[str]:
        return self._preview


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
        RATE_LIMIT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _record_submission(record: Dict[str, Any]) -> None:
    try:
        PROMPT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record["recordedAt"] = _utc_timestamp()
        with PROMPT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Function-based simple handler for dispatcher ---------------------------
def handle_user_prompt_submit(context) -> "HandlerResult":  # type: ignore[name-defined]
    from herald import HandlerResult  # local import to avoid circulars

    payload: Dict[str, Any] = context.payload if isinstance(context.payload, dict) else {}

    # Reuse internal helpers to mirror class behaviour
    prompt, issues = _extract_prompt(payload)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    user_id = payload.get("user_id") or payload.get("userId")
    session_id = payload.get("session_id") or payload.get("sessionId")
    timestamp = payload.get("timestamp") if isinstance(payload.get("timestamp"), str) else _utc_timestamp()

    rate_issue = _check_rate_limit(user_id, session_id)
    if rate_issue:
        issues += (rate_issue,)

    suspicious = _scan_prompt(prompt)
    issues += suspicious

    truncated = False
    sanitized_prompt = prompt.strip()
    if len(sanitized_prompt) > MAX_PROMPT_LENGTH:
        sanitized_prompt = sanitized_prompt[:MAX_PROMPT_LENGTH]
        truncated = True
        issues += ("prompt_truncated",)

    should_alert = bool(issues)

    payload_out = {
        "userPrompt": {
            "prompt": sanitized_prompt,
            "truncated": truncated,
            "length": len(sanitized_prompt),
            "timestamp": timestamp,
        }
    }
    if user_id:
        payload_out["userPrompt"]["userId"] = str(user_id)
    if session_id:
        payload_out["userPrompt"]["sessionId"] = str(session_id)
    if metadata:
        payload_out["userPrompt"]["metadata"] = metadata
    if issues:
        payload_out["userPrompt"]["issues"] = list(dict.fromkeys(issues))
    if should_alert:
        payload_out["userPrompt"]["requiresAttention"] = True

    preview = sanitized_prompt[:MAX_PREVIEW] if sanitized_prompt else None
    _record_submission(
        {
            "timestamp": timestamp,
            "userId": user_id,
            "sessionId": session_id,
            "length": len(sanitized_prompt),
            "issues": list(dict.fromkeys(issues)),
        }
    )

    context_payload = {
        "promptPreview": preview,
        "issues": list(dict.fromkeys(issues)),
        "timestamp": _utc_timestamp(),
    }
    context_payload.update({k: v for k, v in payload_out.get("userPrompt", {}).items() if k not in {"issues", "requiresAttention"}})

    hr = HandlerResult()
    # Map to Claude schema via decision_payload and include hookSpecificOutput for compatibility
    hr.decision_payload = {
        "additionalContext": context_payload,
        "hookSpecificOutput": {
            "hookEventName": USER_PROMPT_SUBMIT,
            "additionalContext": json.dumps(context_payload, ensure_ascii=False),
        },
    }
    # Signal block when issues present
    if issues:
        hr.decision_payload["decision"] = "block"
        hr.decision_payload["reason"] = "Issues detected: " + ", ".join(i.replace("_", " ") for i in issues)
        hr.continue_value = False
    else:
        hr.continue_value = True

    # Audio only on alert
    if should_alert:
        hr.audio_type = USER_PROMPT_SUBMIT
    else:
        hr.suppress_audio = True
    return hr


def main() -> int:
    """CLI entry point for UserPromptSubmit hook."""

    parser = argparse.ArgumentParser(description="Claude Code UserPromptSubmit hook")
    parser.add_argument("--enable-audio", action="store_true", help="Enable actual audio playback")
    parser.add_argument("--json-only", action="store_true", help="Reserved for compatibility; no-op")
    args = parser.parse_args()

    payload, _ = parse_stdin()
    hook = UserPromptSubmitHook()

    result = hook.execute(payload, enable_audio=bool(args.enable_audio), parsed_args=args)

    try:
        log_parts = [
            "[UserPromptSubmit]",
            f"user={payload.get('user_id') or payload.get('userId') or 'anon'}",
            f"issues={','.join(hook.issues) if hook.issues else 'none'}",
            f"alert={hook._should_alert}",
        ]
        if hook.preview:
            log_parts.append(f"preview={hook.preview[:48]}")
        print(" ".join(log_parts), file=sys.stderr)
    except OSError:
        pass

    hook.emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
