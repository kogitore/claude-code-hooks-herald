#!/usr/bin/env python3
"""Centralised constants for Claude Code hook event names and limits."""
from __future__ import annotations

# =============================================================================
# Hook Event Names
# =============================================================================
PRE_TOOL_USE = "PreToolUse"
POST_TOOL_USE = "PostToolUse"
SESSION_START = "SessionStart"
SESSION_END = "SessionEnd"
USER_PROMPT_SUBMIT = "UserPromptSubmit"
NOTIFICATION = "Notification"
STOP = "Stop"
SUBAGENT_STOP = "SubagentStop"
PRE_COMPACT = "PreCompact"

ALL_EVENTS = (
    NOTIFICATION,
    STOP,
    SUBAGENT_STOP,
    PRE_TOOL_USE,
    POST_TOOL_USE,
    USER_PROMPT_SUBMIT,
    SESSION_START,
    SESSION_END,
    PRE_COMPACT,
)

# =============================================================================
# Limits & Thresholds
# =============================================================================
# Command/prompt preview lengths
MAX_COMMAND_PREVIEW = 240
MAX_PROMPT_LENGTH = 4000
MAX_PREVIEW = 240

# Rate limiting
RATE_LIMIT_SECONDS = 1.0
CACHE_CLEANUP_INTERVAL = 300  # 5 minutes
CACHE_ENTRY_TTL = 600  # 10 minutes

# Audio throttle defaults (in seconds)
DEFAULT_THROTTLE_WINDOW = 30

# Output sanitization
MAX_OUTPUT_PREVIEW = 600

# =============================================================================
# Exports
# =============================================================================
__all__ = [
    # Event names
    "PRE_TOOL_USE",
    "POST_TOOL_USE",
    "SESSION_START",
    "SESSION_END",
    "USER_PROMPT_SUBMIT",
    "NOTIFICATION",
    "STOP",
    "SUBAGENT_STOP",
    "PRE_COMPACT",
    "ALL_EVENTS",
    # Limits
    "MAX_COMMAND_PREVIEW",
    "MAX_PROMPT_LENGTH",
    "MAX_PREVIEW",
    "RATE_LIMIT_SECONDS",
    "CACHE_CLEANUP_INTERVAL",
    "CACHE_ENTRY_TTL",
    "DEFAULT_THROTTLE_WINDOW",
    "MAX_OUTPUT_PREVIEW",
]
