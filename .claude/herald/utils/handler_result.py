#!/usr/bin/env python3
"""Minimal HandlerResult for hook functions (Linus-style KISS)."""
from __future__ import annotations


class HandlerResult:
    """Simple result container. No over-engineering."""
    def __init__(self) -> None:
        self.response: dict[str, object] = {}
        self.audio_type: str | None = None
        self.throttle_key: str | None = None
        self.throttle_window: int | None = None
        self.suppress_audio: bool = False
        self.continue_value: bool = True
        self.decision_payload: dict[str, object] | None = None