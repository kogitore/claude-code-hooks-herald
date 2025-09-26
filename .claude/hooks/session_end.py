#!/usr/bin/env python3
"""SessionEnd hook — minimal.

Kept:
 - resource cleanup within session directory
 - state update + event log append
 - JSON additionalContext with removed/skipped
 - audio_type flag

Removed: walls of aspirational nonsense.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.constants import SESSION_END
from utils.session_storage import load_state, write_state, append_event_log
from utils.handler_result import HandlerResult


def handle_session_end(context) -> "HandlerResult":  # type: ignore[name-defined]
    hr = HandlerResult()
    hr.audio_type = SESSION_END
    try:
        summary_json = _finalise_session(context.payload if isinstance(context.payload, dict) else {})
        hr.response["hookSpecificOutput"] = {
            "hookEventName": SESSION_END,
            "additionalContext": summary_json,
        }
    except Exception:
        pass
    return hr


def _finalise_session(context: Dict[str, Any]) -> str:
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

    return context_str

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


def main() -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Claude Code SessionEnd (function)")
    parser.add_argument("--enable-audio", action="store_true")
    _ = parser.parse_args()
    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
    except Exception:
        payload = {}
    from mini_dispatcher import dispatch as mini_dispatch
    response = mini_dispatch(SESSION_END, payload=payload, enable_audio=False)
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
