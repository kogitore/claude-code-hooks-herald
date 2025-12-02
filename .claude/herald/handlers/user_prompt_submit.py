#!/usr/bin/env python3
"""UserPromptSubmit hook - simplified prompt validation and rate limiting."""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from herald.utils.constants import (
    USER_PROMPT_SUBMIT,
    MAX_PROMPT_LENGTH,
    MAX_PREVIEW,
    RATE_LIMIT_SECONDS,
    CACHE_CLEANUP_INTERVAL,
    CACHE_ENTRY_TTL,
)
from herald.utils.handler_result import HandlerResult
from herald.utils.skill_rules import suggest_skills, match_skills, SkillMatch

# Module-level logger
_log = logging.getLogger("hooks.user_prompt_submit")
if not _log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    _log.addHandler(_handler)
    _log.setLevel(logging.WARNING)

PROMPT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "prompt_submissions.jsonl"

SUSPICIOUS_PATTERNS = [
    (re.compile(r"rm\s+-rf\s+", re.IGNORECASE), "dangerous_command"),
    (re.compile(r"drop\s+table", re.IGNORECASE), "sql_drop"),
    (re.compile(r"(https?://)?(?:[\w-]+\.){1,}onion", re.IGNORECASE), "tor_link"),
]

# Skill auto-activation now uses skill_rules.py which loads from skill-rules.json
# See .claude/skills/skill-rules.json for configuration

# Memory-based rate limiting (no disk I/O)
_RATE_LIMIT_CACHE: dict[str, float] = {}
_LAST_CLEANUP = time.time()


def _process_prompt(context: dict[str, object]) -> tuple[dict[str, object], tuple[str, ...], str | None, bool, tuple[str, ...]]:
    """Process user prompt with validation, rate limiting, issue detection, and skill suggestions.

    Returns:
        Tuple of (payload, issues, preview, should_alert, suggested_skills)
    """
    prompt, issues_list = _extract_prompt(context)
    user_id = context.get("user_id") or context.get("userId")
    session_id = context.get("session_id") or context.get("sessionId")
    timestamp = context.get("timestamp") if isinstance(context.get("timestamp"), str) else _utc_timestamp()

    # Collect all issues
    issues_list = list(issues_list)
    rate_issue = _check_rate_limit(user_id, session_id)
    if rate_issue:
        issues_list.append(rate_issue)
    issues_list.extend(_scan_prompt(prompt))

    # Truncate if needed
    sanitized = prompt.strip()
    truncated = len(sanitized) > MAX_PROMPT_LENGTH
    if truncated:
        sanitized = sanitized[:MAX_PROMPT_LENGTH]
        issues_list.append("prompt_truncated")

    # Deduplicate issues (preserve order)
    issues = tuple(dict.fromkeys(issues_list))
    should_alert = bool(issues)

    # Suggest relevant skills based on prompt content
    suggested_skills = _suggest_skills(sanitized)

    # Build payload (flattened structure)
    payload: dict[str, object] = {
        "userPrompt": {
            "prompt": sanitized,
            "truncated": truncated,
            "length": len(sanitized),
            "timestamp": timestamp,
        }
    }
    if user_id:
        payload["userPrompt"]["userId"] = str(user_id)  # type: ignore[index]
    if session_id:
        payload["userPrompt"]["sessionId"] = str(session_id)  # type: ignore[index]
    if metadata := context.get("metadata"):
        if isinstance(metadata, dict):
            payload["userPrompt"]["metadata"] = metadata  # type: ignore[index]
    if issues:
        payload["userPrompt"]["issues"] = list(issues)  # type: ignore[index]
        payload["userPrompt"]["requiresAttention"] = True  # type: ignore[index]
    if suggested_skills:
        payload["userPrompt"]["suggestedSkills"] = list(suggested_skills)  # type: ignore[index]

    preview = sanitized[:MAX_PREVIEW] if sanitized else None

    # Log submission
    _record_submission({
        "timestamp": timestamp,
        "userId": user_id,
        "sessionId": session_id,
        "length": len(sanitized),
        "issues": list(issues),
        "suggestedSkills": list(suggested_skills),
    })
    return payload, issues, preview, should_alert, suggested_skills


def _extract_prompt(context: dict[str, object]) -> tuple[str, tuple[str, ...]]:
    """Extract prompt from context."""
    prompt = context.get("prompt")
    if isinstance(prompt, str):
        cleaned = prompt.replace("\r\n", "\n")
        return cleaned, tuple()
    return "", ("missing_prompt",)


def _scan_prompt(prompt: str) -> tuple[str, ...]:
    """Scan prompt for suspicious patterns."""
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


def _suggest_skills(prompt: str) -> tuple[str, ...]:
    """Suggest relevant skills based on prompt content.

    Based on Skill Auto-Activation pattern from claude-code-infrastructure-showcase.
    Now loads rules from .claude/skills/skill-rules.json for flexible configuration.

    Returns:
        Tuple of skill names that match keywords or intent patterns in the prompt.
    """
    return suggest_skills(prompt)


def _check_rate_limit(user_id: object, session_id: object) -> str | None:
    """Memory-based rate limiting with automatic cache cleanup.

    Cleanup now removes only expired entries instead of clearing all,
    preventing rate limit bypass during cleanup moments.
    """
    global _LAST_CLEANUP
    ref = str(user_id or session_id or "global")
    now = time.time()

    # Periodic cleanup: remove only expired entries (not all)
    if now - _LAST_CLEANUP > CACHE_CLEANUP_INTERVAL:
        expired_keys = [k for k, v in _RATE_LIMIT_CACHE.items() if now - v > CACHE_ENTRY_TTL]
        for k in expired_keys:
            del _RATE_LIMIT_CACHE[k]
        _LAST_CLEANUP = now
        if expired_keys:
            _log.debug("Cleaned %d expired rate limit entries", len(expired_keys))

    last = _RATE_LIMIT_CACHE.get(ref)
    _RATE_LIMIT_CACHE[ref] = now

    if isinstance(last, (int, float)) and now - float(last) < RATE_LIMIT_SECONDS:
        return "rate_limited"
    return None


def _record_submission(record: dict[str, object]) -> None:
    """Record prompt submission to log file."""
    try:
        PROMPT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record["recordedAt"] = _utc_timestamp()
        with PROMPT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")
    except OSError as e:
        _log.warning("Failed to record prompt submission: %s", e)


def _utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def handle_user_prompt_submit(context) -> HandlerResult:
    """Handle user prompt submit event - validation, rate limiting, and skill suggestions."""
    payload: dict[str, object] = context.payload if isinstance(context.payload, dict) else {}
    processed_payload, issues, preview, should_alert, suggested_skills = _process_prompt(payload)
    base = processed_payload.get("userPrompt", {})

    ctx: dict[str, object] = {
        "promptPreview": preview,
        "issues": list(issues),
        "timestamp": _utc_timestamp(),
    }
    # Merge base items except issues and requiresAttention
    if isinstance(base, dict):
        for k, v in base.items():
            if k not in {"issues", "requiresAttention"}:
                ctx[k] = v

    # Include skill suggestions in context
    if suggested_skills:
        ctx["suggestedSkills"] = list(suggested_skills)

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


def main() -> int:
    """Entry point for manual invocations."""
    parser = argparse.ArgumentParser(description="Claude Code UserPromptSubmit hook")
    parser.add_argument("--enable-audio", action="store_true",
                       help="Enable audio feedback")
    _ = parser.parse_args()

    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
    except Exception:
        payload = {}

    from herald.dispatcher import dispatch
    response = dispatch(USER_PROMPT_SUBMIT, payload=payload)
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
