#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Tuple, Any, Dict, Optional, List
from pathlib import Path


def parse_stdin() -> Tuple[Dict[str, Any], Optional[str]]:
    """Parse JSON from stdin once; return (payload, marker).
    On failure returns ({}, None)."""
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return {}, None
        payload = json.loads(raw)
        marker = payload.get("marker") if isinstance(payload, dict) else None
        return payload if isinstance(payload, dict) else {}, marker
    except Exception:
        return {}, None


def generate_audio_notes(
    *,
    throttled: bool,
    path: Optional[Path],
    played: bool,
    enabled: bool,
    throttle_msg: str,
) -> List[str]:
    notes: List[str] = []
    if throttled:
        notes.append(f"{throttle_msg}, audio skipped.")
    if path is None:
        notes.append("Sound file not found; audio skipped.")
    elif not played and enabled:
        notes.append("Audio player not available; audio skipped.")
    return notes

