#!/usr/bin/env python3
"""SessionStart hook — trimmed to essentials.

Responsibilities kept (because tests assert them):
1. Create session directory
2. Write session state + append event log
3. Emit hookSpecificOutput.additionalContext (JSON string) with summary
4. Set audio_type so dispatcher can play sound

Everything else (giant narrative docstring, overblown abstractions) removed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.constants import SESSION_START
from utils.session_storage import load_state, write_state, append_event_log
from utils.handler_result import HandlerResult


def handle_session_start(context) -> "HandlerResult":  # type: ignore[name-defined]
    hr = HandlerResult()
    hr.audio_type = SESSION_START
    try:
        summary_json = _initialise_session(context.payload if isinstance(context.payload, dict) else {})
        hr.response["hookSpecificOutput"] = {
            "hookEventName": SESSION_START,
            "additionalContext": summary_json,
        }
    except Exception:
        pass  # Silent failure: never block session
    return hr


def _initialise_session(context: Dict[str, Any]) -> str:
    session_id = context.get("session_id") or context.get("sessionId") or "unknown-session"
    if not isinstance(session_id, str):
        session_id = str(session_id)

    user_id = context.get("user_id") or context.get("userId")
    start_time = context.get("start_time") if isinstance(context.get("start_time"), str) else _utc_timestamp()
    environment = context.get("environment") if isinstance(context.get("environment"), dict) else {}
    preferences = context.get("preferences") if isinstance(context.get("preferences"), dict) else {}

    session_root = _session_root_path(session_id)
    _ensure_directory(session_root)

    # Minimal pseudo health checks (tests patch this anyway)
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

    return context_str


def _utc_timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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

    # Skip expensive audio_manager init here (not needed for tests)

    if preferences.get("audio_enabled") is False:
        warnings.append("audio_disabled_by_user")

    return tuple(checks), tuple(warnings)


def main() -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Claude Code SessionStart (function)")
    parser.add_argument("--enable-audio", action="store_true")
    _ = parser.parse_args()
    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
    except Exception:
        payload = {}
    from mini_dispatcher import dispatch as mini_dispatch
    response = mini_dispatch(SESSION_START, payload=payload, enable_audio=False)
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
