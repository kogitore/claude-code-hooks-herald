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

from utils.base_hook import BaseHook, HookExecutionResult
from utils.common_io import parse_stdin
from utils.session_storage import append_event_log, load_state, utc_timestamp, write_state


@dataclass
class SessionEndResult:
    context: str
    removed_resources: Tuple[str, ...]
    skipped_resources: Tuple[str, ...]


class SessionEndHook(BaseHook):
    """SessionEnd hook for session cleanup and finalization."""

    default_audio_event = "SessionEnd"
    default_throttle_seconds = 5

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._removed: Tuple[str, ...] = ()
        self._skipped: Tuple[str, ...] = ()

    # -- BaseHook overrides ---------------------------------------------
    def validate_input(self, data: Dict[str, Any]) -> bool:  # type: ignore[override]
        return isinstance(data, dict)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[override]
        """Legacy compatibility path (unused)."""
        return {}

    def handle_error(self, error: Exception) -> Dict[str, Any]:  # type: ignore[override]
        self._removed = ()
        self._skipped = ("cleanup_exception",)
        return {
            "sessionSummary": {
                "status": "error",
                "reason": type(error).__name__,
            }
        }

    # -- Custom behaviour -----------------------------------------------
    def handle_hook_logic(
        self,
        context: Dict[str, Any],
        *,
        parsed_args: Optional[argparse.Namespace] = None,
    ) -> HookExecutionResult:
        result = self._finalise_session(context)
        self._removed = result.removed_resources
        self._skipped = result.skipped_resources

        hook_result = HookExecutionResult()
        hook_result.payload["hookSpecificOutput"] = {
            "hookEventName": "SessionEnd",
            "additionalContext": result.context,
        }
        if result.skipped_resources:
            hook_result.notes.append("session_end_skipped_cleanup")
        return hook_result

    def _finalise_session(self, context: Dict[str, Any]) -> SessionEndResult:
        session_id = context.get("session_id") or context.get("sessionId") or "unknown-session"
        if not isinstance(session_id, str):
            session_id = str(session_id)

        end_time = context.get("end_time") if isinstance(context.get("end_time"), str) else utc_timestamp()
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

    @property
    def removed(self) -> Tuple[str, ...]:
        return self._removed

    @property
    def skipped(self) -> Tuple[str, ...]:
        return self._skipped


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


def main() -> int:
    """CLI entry point for SessionEnd hook."""

    parser = argparse.ArgumentParser(description="Claude Code SessionEnd hook")
    parser.add_argument("--enable-audio", action="store_true", help="Enable actual audio playback")
    parser.add_argument("--json-only", action="store_true", help="Reserved for compatibility; no-op")
    args = parser.parse_args()

    payload, _ = parse_stdin()
    hook = SessionEndHook()

    result = hook.execute(payload, enable_audio=bool(args.enable_audio), parsed_args=args)

    try:
        log_parts = [
            "[SessionEnd]",
            f"session={payload.get('session_id') or payload.get('sessionId') or 'unknown'}",
            f"removed={len(hook.removed)}",
            f"skipped={len(hook.skipped)}",
        ]
        print(" ".join(log_parts), file=sys.stderr)
    except OSError:
        pass

    hook.emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
