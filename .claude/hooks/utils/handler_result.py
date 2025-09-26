#!/usr/bin/env python3
"""Minimal HandlerResult for hook functions (Linus-style KISS)."""
from __future__ import annotations

from typing import Any, Dict, Optional


class HandlerResult:
    """Simple result container. No over-engineering."""
    def __init__(self) -> None:
        self.response: Dict[str, Any] = {}
        self.audio_type: Optional[str] = None
        self.throttle_key: Optional[str] = None
        self.throttle_window: Optional[int] = None
        self.suppress_audio: bool = False
        self.continue_value: bool = True
        self.decision_payload: Optional[Dict[str, Any]] = None