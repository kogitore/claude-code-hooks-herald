#!/usr/bin/env python3
"""Minimal session storage (Linus-style KISS version).

Simple file-based state and event logging. No over-engineering.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


# Base paths
_LOGS_ROOT = Path(__file__).resolve().parents[2] / "logs"
STATE_PATH = _LOGS_ROOT / "session_state.json"
EVENT_LOG_PATH = _LOGS_ROOT / "session_events.jsonl"


def load_state() -> Dict[str, Any]:
    """Load session state. Return {} if not found."""
    try:
        _LOGS_ROOT.mkdir(parents=True, exist_ok=True)
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
    except Exception:
        pass
    return {}


def write_state(state: Dict[str, Any]) -> None:
    """Write session state to disk."""
    try:
        _LOGS_ROOT.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def append_event_log(event: Dict[str, Any]) -> None:
    """Append event to log file."""
    try:
        _LOGS_ROOT.mkdir(parents=True, exist_ok=True)
        with EVENT_LOG_PATH.open("a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass