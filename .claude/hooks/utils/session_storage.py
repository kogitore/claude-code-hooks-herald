#!/usr/bin/env python3
"""Shared session storage helpers for Claude Code hooks."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_LOGS_ROOT = Path(__file__).resolve().parents[2] / "logs"
STATE_PATH: Path = _LOGS_ROOT / "session_state.json"
EVENT_LOG_PATH: Path = _LOGS_ROOT / "session_events.jsonl"


def utc_timestamp() -> str:
    """Generate a UTC ISO 8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def load_state() -> Dict[str, Any]:
    """Load the persisted session state map."""
    if not STATE_PATH.exists():
        return {}
    try:
        content = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return content if isinstance(content, dict) else {}


def write_state(state: Dict[str, Any]) -> None:
    """Persist the session state map to disk."""
    try:
        _LOGS_ROOT.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def append_event_log(record: Dict[str, Any]) -> None:
    """Append a single event record to the session log."""
    try:
        _LOGS_ROOT.mkdir(parents=True, exist_ok=True)
        with EVENT_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


__all__ = [
    "EVENT_LOG_PATH",
    "STATE_PATH",
    "append_event_log",
    "load_state",
    "utc_timestamp",
    "write_state",
]
