#!/usr/bin/env python3
"""Minimal session storage utilities for session lifecycle hooks.

Provides a simple file-based state and event log under logs/.
Paths can be overridden in tests by monkeypatching module globals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# Base logs directory (can be patched in tests)
_LOGS_ROOT: Path = (Path(__file__).resolve().parents[2] / "logs").resolve()

# Public paths (tests patch these)
STATE_PATH: Path = _LOGS_ROOT / "session_state.json"
EVENT_LOG_PATH: Path = _LOGS_ROOT / "session_events.jsonl"


def _ensure_logs_dir() -> None:
    try:
        _LOGS_ROOT.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def load_state() -> Dict[str, Any]:
    """Load the session state dictionary from disk; return {} if missing/invalid."""
    try:
        if STATE_PATH.exists():
            with STATE_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def write_state(state: Dict[str, Any]) -> None:
    """Persist the provided session state dictionary to disk."""
    _ensure_logs_dir()
    try:
        with STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def append_event_log(event: Dict[str, Any]) -> None:
    """Append a single JSON line to the event log file."""
    _ensure_logs_dir()
    try:
        with EVENT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


__all__ = [
    "_LOGS_ROOT",
    "STATE_PATH",
    "EVENT_LOG_PATH",
    "load_state",
    "write_state",
    "append_event_log",
]
