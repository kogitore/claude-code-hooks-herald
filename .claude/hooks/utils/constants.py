#!/usr/bin/env python3
"""Centralised constants for Claude Code hook event names."""
from __future__ import annotations

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


__all__ = [
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
]
