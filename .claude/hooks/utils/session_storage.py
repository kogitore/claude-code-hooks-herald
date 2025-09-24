#!/usr/bin/env python3
"""Minimal no-op session storage to keep imports working during Phase 1.
This replaces the over-engineered session_storage with simple stubs.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, Any
from pathlib import Path

# Default paths under logs/ for compatibility
_LOGS_ROOT = Path(__file__).resolve().parents[3] / "logs"
STATE_PATH = _LOGS_ROOT / "session_state.json"
EVENT_LOG_PATH = _LOGS_ROOT / "session_events.jsonl"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> Dict[str, Any]:
    try:
        if STATE_PATH.exists():
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def write_state(state: Dict[str, Any]) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Use Path.write_text to align with tests that patch this method
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        # Swallow permission or IO errors per test expectations
        pass


def append_event_log(entry: Dict[str, Any]) -> None:
    try:
        EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
