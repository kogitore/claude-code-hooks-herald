#!/usr/bin/env python3
"""SessionStart hook for session initialization and setup.

This hook is triggered when a new Claude Code session begins and handles:
- Session initialization and setup
- User environment preparation
- Resource allocation and cleanup
- Welcome notifications and audio cues

IMPLEMENTATION REQUIREMENTS for Codex:
1. Inherit from BaseHook with default_audio_event = "SessionStart"
2. Implement handle_hook_logic() method that:
   - Initializes session-specific resources
   - Sets up user environment and preferences
   - Performs initial system health checks
   - Returns HookExecutionResult with session info
3. Handle session setup tasks:
   - Create session directories and temp files
   - Load user preferences and configurations
   - Initialize session-scoped caches
   - Verify system dependencies
4. Audio integration:
   - Welcome notification sounds
   - System readiness confirmation
   - Error alerts for setup failures

CONTEXT FORMAT:
{
    "session_id": "uuid-string",
    "user_id": "uuid-string",
    "start_time": "2025-01-01T00:00:00Z",
    "environment": {
        "platform": "darwin|linux|windows",
        "python_version": "3.9.6",
        "working_directory": "/path/to/project"
    },
    "preferences": {
        "audio_enabled": true,
        "volume": 0.2,
        "language": "en"
    }
}

CRITICAL NOTES:
- Session setup should be fast to avoid startup delays
- Handle environment detection and adaptation
- Create necessary session resources safely
- Validate system requirements and dependencies
- Provide clear feedback for setup failures
- Consider cleanup of previous session remnants
- Be prepared for concurrent session starts
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.audio_manager import AudioManager
from utils.base_hook import BaseHook, HookExecutionResult
from utils.common_io import parse_stdin
from utils.session_storage import append_event_log, load_state, utc_timestamp, write_state


@dataclass
class SessionStartResult:
    context: str
    checks: Tuple[str, ...]
    warnings: Tuple[str, ...]


class SessionStartHook(BaseHook):
    """SessionStart hook for session initialization and setup."""

    default_audio_event = "SessionStart"
    default_throttle_seconds = 5

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._checks: Tuple[str, ...] = ()
        self._warnings: Tuple[str, ...] = ()

    # -- BaseHook overrides ---------------------------------------------
    def validate_input(self, data: Dict[str, Any]) -> bool:  # type: ignore[override]
        return isinstance(data, dict)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[override]
        """Legacy compatibility path (unused)."""
        return {}

    def handle_error(self, error: Exception) -> Dict[str, Any]:  # type: ignore[override]
        self._checks = ()
        self._warnings = ("session_start_exception",)
        return {
            "session": {
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
        result = self._initialise_session(context)
        self._checks = result.checks
        self._warnings = result.warnings

        hook_result = HookExecutionResult()
        hook_result.payload["hookSpecificOutput"] = {
            "hookEventName": "SessionStart",
            "additionalContext": result.context,
        }
        if result.warnings:
            hook_result.notes.append("session_start_warnings")
        return hook_result

    def _initialise_session(self, context: Dict[str, Any]) -> SessionStartResult:
        session_id = context.get("session_id") or context.get("sessionId") or "unknown-session"
        if not isinstance(session_id, str):
            session_id = str(session_id)

        user_id = context.get("user_id") or context.get("userId")
        start_time = context.get("start_time") if isinstance(context.get("start_time"), str) else utc_timestamp()
        environment = context.get("environment") if isinstance(context.get("environment"), dict) else {}
        preferences = context.get("preferences") if isinstance(context.get("preferences"), dict) else {}

        session_root = _session_root_path(session_id)
        _ensure_directory(session_root)

        checks, warnings = _run_health_checks(environment, preferences)

        state = load_state()
        state[session_id] = {
            "sessionId": session_id,
            "userId": user_id,
            "startedAt": start_time,
            "environment": environment,
            "preferences": preferences,
            "state": {"status": "active"},
            "history": [
                {
                    "event": "session_start",
                    "timestamp": start_time,
                    "checks": checks,
                    "warnings": warnings,
                }
            ],
        }
        write_state(state)
        append_event_log(
            {
                "sessionId": session_id,
                "event": "session_start",
                "timestamp": start_time,
                "checks": checks,
                "warnings": warnings,
            }
        )

        session_summary = {
            "sessionId": session_id,
            "userId": user_id,
            "startedAt": start_time,
            "setupChecks": list(checks),
            "warnings": list(warnings),
            "workspace": str(session_root),
        }
        if preferences:
            session_summary["preferences"] = preferences
        if environment:
            session_summary["environment"] = environment

        context_str = json.dumps(session_summary, ensure_ascii=False)

        return SessionStartResult(context=context_str, checks=checks, warnings=warnings)

    @property
    def checks(self) -> Tuple[str, ...]:
        return self._checks

    @property
    def warnings(self) -> Tuple[str, ...]:
        return self._warnings


def _session_root_path(session_id: str) -> Path:
    base = Path(os.environ.get("CLAUDE_SESSION_ROOT", "logs/sessions"))
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[2] / base
    return base / session_id


def _ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _run_health_checks(environment: Dict[str, Any], preferences: Dict[str, Any]) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    checks: List[str] = []
    warnings: List[str] = []

    working_dir = environment.get("working_directory") if isinstance(environment, dict) else None
    if isinstance(working_dir, str):
        path = Path(working_dir)
        if path.exists():
            checks.append("working_directory_exists")
        else:
            warnings.append("working_directory_missing")

    audio_dir = Path(__file__).resolve().parents[1] / "sounds"
    if audio_dir.exists():
        checks.append("sounds_directory_present")
    else:
        warnings.append("sounds_directory_missing")

    audio_manager = AudioManager()
    if getattr(audio_manager, "_player_cmd", None):
        checks.append("audio_player_detected")
    else:
        warnings.append("audio_player_not_found")

    if preferences.get("audio_enabled") is False:
        warnings.append("audio_disabled_by_user")

    return tuple(checks), tuple(warnings)


def main() -> int:
    """CLI entry point for SessionStart hook."""

    parser = argparse.ArgumentParser(description="Claude Code SessionStart hook")
    parser.add_argument("--enable-audio", action="store_true", help="Enable actual audio playback")
    parser.add_argument("--json-only", action="store_true", help="Reserved for compatibility; no-op")
    args = parser.parse_args()

    payload, _ = parse_stdin()
    hook = SessionStartHook()

    result = hook.execute(payload, enable_audio=bool(args.enable_audio), parsed_args=args)

    try:
        log_parts = [
            "[SessionStart]",
            f"session={payload.get('session_id') or payload.get('sessionId') or 'unknown'}",
            f"checks={','.join(hook.checks) if hook.checks else 'none'}",
        ]
        if hook.warnings:
            log_parts.append(f"warnings={','.join(hook.warnings)}")
        print(" ".join(log_parts), file=sys.stderr)
    except OSError:
        pass

    hook.emit_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
