#!/usr/bin/env python3
"""Simplified Decision API (Linus-style KISS version).

The original was 382 lines of over-engineered complexity.
This version: Simple pattern matching. No ceremony.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Any, Tuple


class DecisionAPI:
    """Simple decision maker. No over-engineering."""

    def __init__(self):
        # Simple built-in patterns for common dangerous commands
        self.dangerous_patterns = [
            r'\brm\s+-rf\s+/',           # rm -rf /
            r'\brm\s+-rf\s+\*',         # rm -rf *
            r'>\s*/dev/sd[a-z]',        # > /dev/sda
            r'\bdd\s+.*of=/dev/sd[a-z]', # dd to disk
            r':\(\)\{.*\}:',            # fork bomb
            r'\bmkfs\.',                # format filesystem
            r'\bfdisk\s+/dev',          # disk partitioning
        ]

    def evaluate_safety(self, tool_name: str, command: str, **kwargs) -> Tuple[str, Optional[str]]:
        """Evaluate command safety. Returns (decision, reason)."""
        if not command or not isinstance(command, str):
            return "allow", None

        command = command.strip()

        # Check dangerous patterns
        for pattern in self.dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return "deny", f"Dangerous command pattern detected: {pattern}"

        # Check for potential destructive operations
        destructive_keywords = ['rm ', 'rmdir ', 'del ', 'format ', 'fdisk ', 'mkfs.']
        for keyword in destructive_keywords:
            if keyword in command.lower():
                # Only warn about destructive commands in sensitive paths
                sensitive_paths = ['/', '/bin', '/usr', '/etc', '/var', '/sys']
                for path in sensitive_paths:
                    if path in command:
                        return "ask", f"Potentially destructive command affecting system path: {path}"

        return "allow", None

    def should_prompt_user(self, tool_name: str, tool_input: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Check if user prompt is needed."""
        command = tool_input.get("command", "")
        decision, reason = self.evaluate_safety(tool_name, command)

        if decision == "deny":
            return False, reason  # Block completely
        elif decision == "ask":
            return True, reason   # Ask user
        else:
            return False, None    # Allow silently

    # Legacy compatibility methods
    def evaluate(self, tool_name: str, tool_input: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Legacy evaluate method."""
        command = tool_input.get("command", "")
        decision, reason = self.evaluate_safety(tool_name, command)

        return {
            "decision": decision,
            "reason": reason,
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }

    def check_safety(self, tool_name: str, command: str) -> str:
        """Simple safety check. Returns 'allow', 'ask', or 'deny'."""
        decision, _ = self.evaluate_safety(tool_name, command)
        return decision

    def pre_tool_use_decision(self, tool_name: str, tool_input: Dict[str, Any]) -> "DecisionResult":
        """Make decision for pre tool use."""
        if not tool_input:
            return self.allow("No tool input to evaluate", event="PreToolUse")

        command = tool_input.get("command", "")
        if not command:
            return self.allow("No command to evaluate", event="PreToolUse")

        decision, reason = self.evaluate_safety(tool_name, command)

        if decision == "deny":
            return self.deny(reason or "Dangerous command detected", event="PreToolUse")
        elif decision == "ask":
            return self.ask(reason or "Command requires confirmation", event="PreToolUse")
        else:
            return self.allow("Command is safe", event="PreToolUse")

    def allow(self, reason: str, event: str = "", **kwargs) -> "DecisionResult":
        """Create allow decision."""
        return DecisionResult("allow", reason, blocked=False, **kwargs)

    def deny(self, reason: str, event: str = "", **kwargs) -> "DecisionResult":
        """Create deny decision."""
        return DecisionResult("deny", reason, blocked=True, **kwargs)

    def ask(self, reason: str, event: str = "", **kwargs) -> "DecisionResult":
        """Create ask decision."""
        return DecisionResult("ask", reason, blocked=False, **kwargs)


class DecisionResult:
    """Simple decision result."""
    def __init__(self, decision: str, reason: str, blocked: bool = False, **kwargs):
        self.decision = decision
        self.reason = reason
        self.blocked = blocked
        self.additional_context = kwargs
        # Set up payload for backward compatibility
        self.payload = {
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
            "decision": decision,
            "continue": not blocked,
            "additionalContext": kwargs
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "decision": self.decision,
            "reason": self.reason,
            "blocked": self.blocked,
            "permissionDecision": self.decision,
            "permissionDecisionReason": self.reason,
            "continue": not self.blocked,
            "additionalContext": self.additional_context
        }