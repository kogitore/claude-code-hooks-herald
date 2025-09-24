#!/usr/bin/env python3
"""SessionEnd hook for session cleanup and finalization.

This hook is triggered when a Claude Code session ends and handles:
- Session cleanup and resource deallocation
- Final data persistence and backup
- Usage statistics and reporting
- Farewell notifications and audio cues

IMPLEMENTATION REQUIREMENTS for Codex:
1. Inherit from BaseHook with default_audio_event = "SessionEnd"
2. Implement handle_hook_logic() method that:
   - Performs session cleanup and resource deallocation
   - Saves session data and statistics
   - Clears temporary files and caches
   - Returns HookExecutionResult with cleanup status
3. Handle session teardown tasks:
   - Clean up temporary files and directories
   - Save session state and preferences
   - Generate session summary and statistics
   - Release system resources
4. Audio integration:
   - Session completion notification sounds
   - Different cues for normal vs. error termination
   - Final confirmation of successful cleanup

CONTEXT FORMAT:
{
    "session_id": "uuid-string",
    "user_id": "uuid-string",
    "end_time": "2025-01-01T00:00:00Z",
    "duration": 3600,  // seconds
    "termination_reason": "normal|error|timeout|forced",
    "statistics": {
        "tools_used": 42,
        "prompts_submitted": 15,
        "errors_encountered": 2
    },
    "resources_to_cleanup": [
        "/tmp/session-uuid/...",
        "cache_entries",
        ...
    ]
}

CRITICAL NOTES:
- Session cleanup should be reliable even in error conditions
- Save important session data before cleanup
- Handle partial cleanup scenarios gracefully
- Consider data privacy when saving session information
- Be prepared for interrupted or forced terminations
- Provide clear feedback for cleanup status
- Handle concurrent session end scenarios
- Consider session data archival policies
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.constants import SESSION_END
from utils.session_storage import load_state, write_state, append_event_log


# --- Function-based simple handler for dispatcher ---------------------------
def handle_session_end(context) -> "HandlerResult":  # type: ignore[name-defined]
    from herald import HandlerResult  # local import to avoid circulars
    hr = HandlerResult()
    hr.audio_type = SESSION_END
    try:
        result = _finalise_session(context.payload if isinstance(context.payload, dict) else {})
        hr.response["hookSpecificOutput"] = {
            "hookEventName": SESSION_END,
            "additionalContext": result.context,
        }
    except Exception:
        pass
    return hr


@dataclass
class SessionEndResult:
    context: str
    removed_resources: Tuple[str, ...]
    skipped_resources: Tuple[str, ...]


    # Class-based hook removed in Phase 3

def _finalise_session(context: Dict[str, Any]) -> SessionEndResult:
    session_id = context.get("session_id") or context.get("sessionId") or "unknown-session"
    if not isinstance(session_id, str):
        session_id = str(session_id)

    end_time = context.get("end_time") if isinstance(context.get("end_time"), str) else _utc_timestamp()
    duration = _parse_duration(context.get("duration"))
    termination_reason = context.get("termination_reason") or context.get("reason") or "normal"
    statistics = context.get("statistics") if isinstance(context.get("statistics"), dict) else {}
    resources = context.get("resources_to_cleanup") or context.get("cleanup" ) or []
    if not isinstance(resources, list):
        resources = []

    removed, skipped = _cleanup_resources(session_id, resources)

    state = load_state()
    session_entry = state.get(session_id, {}) if isinstance(state, dict) else {}
    session_entry.setdefault("state", {})
    session_entry["state"].update({"status": "ended", "endedAt": end_time, "termination": termination_reason})
    if duration is not None:
        session_entry["state"]["durationSeconds"] = duration
    session_entry.setdefault("history", []).append(
        {
            "event": "session_end",
            "timestamp": end_time,
            "termination": termination_reason,
            "removed": removed,
            "skipped": skipped,
        }
    )
    session_entry["statistics"] = statistics
    state[session_id] = session_entry
    write_state(state)
    append_event_log(
        {
            "sessionId": session_id,
            "event": "session_end",
            "timestamp": end_time,
            "termination": termination_reason,
            "removed": removed,
            "skipped": skipped,
        }
    )

    summary = {
        "sessionId": session_id,
        "endedAt": end_time,
        "termination": termination_reason,
        "durationSeconds": duration,
        "statistics": statistics,
        "removedResources": list(removed),
        "skippedResources": list(skipped),
    }

    context_str = json.dumps(summary, ensure_ascii=False)

    return SessionEndResult(context=context_str, removed_resources=removed, skipped_resources=skipped)

    # Properties removed with class


def _parse_duration(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _cleanup_resources(session_id: str, resources: List[Any]) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    removed: List[str] = []
    skipped: List[str] = []
    base = _session_root_path(session_id)
    for item in resources:
        if not isinstance(item, str):
            continue
        candidate = Path(item)
        if not candidate.is_absolute():
            candidate = base / candidate
        try:
            candidate = candidate.resolve()
        except Exception:
            skipped.append(item)
            continue
        try:
            if base in candidate.parents or candidate == base:
                if candidate.is_dir():
                    shutil.rmtree(candidate, ignore_errors=True)
                elif candidate.exists():
                    candidate.unlink(missing_ok=True)
                removed.append(str(candidate))
            else:
                skipped.append(str(candidate))
        except Exception:
            skipped.append(str(candidate))
    return tuple(removed), tuple(skipped)


def _session_root_path(session_id: str) -> Path:
    base = Path("logs/sessions")
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[2] / base
    return base / session_id


def _utc_timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:  # pragma: no cover - simple CLI passthrough
    parser = argparse.ArgumentParser(description="Claude Code SessionEnd (function)")
    parser.add_argument("--enable-audio", action="store_true")
    _ = parser.parse_args()
    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
    except Exception:
        payload = {}
    from herald import build_default_dispatcher
    disp = build_default_dispatcher()
    report = disp.dispatch(SESSION_END, payload=payload)
    print(json.dumps(report.response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
