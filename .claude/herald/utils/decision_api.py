#!/usr/bin/env python3
"""Simplified Decision API (Linus-style KISS version).

The original was 382 lines of over-engineered complexity.
This version: Simple pattern matching. No ceremony.

SECURITY LIMITATION:
    This provides BASIC protection only. Advanced bypass techniques are NOT detected:
    - Command substitution: $(echo rm) -rf /
    - Quoting tricks: "rm" "-rf" "/"
    - Backslash escapes: \\rm -rf /
    - Flag reordering: rm -r -f /
    - Encoding/obfuscation

    For production security, consider external tools like shellcheck, bandit, or semgrep.
"""
from __future__ import annotations

import logging
import re
import shlex
import sys

# Module-level logger (writes to stderr, won't pollute JSON output)
_log = logging.getLogger("hooks.decision_api")
if not _log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    _log.addHandler(_handler)
    _log.setLevel(logging.WARNING)


class DecisionAPI:
    """Simple decision maker. No over-engineering."""

    # Sensitive system paths that require extra caution
    SENSITIVE_PATHS: tuple[str, ...] = ("/", "/bin", "/usr", "/etc", "/var", "/sys", "/boot", "/lib")

    # Dangerous command base names (checked after shlex parsing)
    DANGEROUS_COMMANDS: tuple[str, ...] = ("rm", "\\rm", "rmdir", "dd", "mkfs", "fdisk", "format")

    def __init__(self) -> None:
        # Regex patterns for dangerous commands (fallback when shlex fails)
        self.dangerous_patterns: list[str] = [
            r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)*(-[a-zA-Z]*f[a-zA-Z]*\s+)*[/~]",  # rm with -r/-f targeting root
            r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)*(-[a-zA-Z]*r[a-zA-Z]*\s+)*[/~]",  # rm with -f/-r (reversed)
            r">\s*/dev/sd[a-z]",         # > /dev/sda
            r"\bdd\s+.*of=/dev/sd[a-z]",  # dd to disk
            r":\(\)\{.*\}:;?:",          # fork bomb (improved pattern)
            r"\bmkfs\.",                  # format filesystem
            r"\bfdisk\s+/dev",            # disk partitioning
        ]

    def evaluate(self, tool_name: str, tool_input: dict[str, object], **kwargs: object) -> dict[str, object]:
        """Unified evaluation method. Returns decision dict with permission fields."""
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else str(tool_input)
        command_str = str(command) if command else ""
        decision, reason = self._check_command_safety(command_str)

        return {
            "decision": decision,
            "reason": reason,
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }

    def _check_command_safety(self, command: str) -> tuple[str, str | None]:
        """Evaluate command safety using shlex parsing with regex fallback.

        Returns:
            Tuple of (decision, reason) where decision is 'allow', 'ask', or 'deny'.
        """
        if not command or not isinstance(command, str):
            return "allow", None

        command = command.strip()
        if not command:
            return "allow", None

        # Try shlex parsing first (more accurate)
        tokens: list[str] | None = None
        try:
            tokens = shlex.split(command)
        except ValueError as e:
            _log.debug("shlex parse failed for command: %s", e)
            # Fall through to regex-based detection

        # Token-based analysis (if parsing succeeded)
        if tokens:
            result = self._check_tokens(tokens, command)
            if result[0] != "allow":
                return result

        # Regex fallback (catches some bypass attempts)
        for pattern in self.dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return "deny", f"Dangerous command pattern detected: {pattern}"

        # Check for destructive keywords in sensitive paths
        return self._check_destructive_paths(command)

    def _check_tokens(self, tokens: list[str], original_cmd: str) -> tuple[str, str | None]:
        """Analyze parsed tokens for dangerous patterns."""
        if not tokens:
            return "allow", None

        base_cmd = tokens[0].lstrip("\\")  # Handle \rm escape

        # Check if it's a dangerous base command
        if base_cmd not in self.DANGEROUS_COMMANDS:
            return "allow", None

        # rm/rmdir specific checks
        if base_cmd in ("rm", "rmdir"):
            has_recursive = any(
                t.startswith("-") and "r" in t.lower()
                for t in tokens[1:]
                if not t.startswith("--")
            ) or "--recursive" in tokens

            has_force = any(
                t.startswith("-") and "f" in t.lower()
                for t in tokens[1:]
                if not t.startswith("--")
            ) or "--force" in tokens

            # Get target paths (non-flag arguments)
            targets = [t for t in tokens[1:] if not t.startswith("-")]

            for target in targets:
                # Normalize path for checking
                normalized = target.rstrip("/")
                if normalized in self.SENSITIVE_PATHS or normalized == "":
                    if has_recursive and has_force:
                        return "deny", f"Destructive rm -rf targeting sensitive path: {target}"
                    if has_recursive or has_force:
                        return "ask", f"Potentially destructive rm on sensitive path: {target}"

        # dd specific checks
        if base_cmd == "dd":
            for token in tokens:
                if token.startswith("of=/dev/"):
                    return "deny", f"dd writing to device: {token}"

        return "allow", None

    def _check_destructive_paths(self, command: str) -> tuple[str, str | None]:
        """Check for destructive operations in sensitive paths (fallback)."""
        destructive_keywords = ("rm ", "rmdir ", "del ", "format ", "fdisk ", "mkfs.")
        lowered = command.lower()

        for keyword in destructive_keywords:
            if keyword in lowered:
                for path in self.SENSITIVE_PATHS:
                    if path in command:
                        return "ask", f"Potentially destructive command affecting system path: {path}"

        return "allow", None

    # Backward compatibility aliases (deprecated - use evaluate() instead)
    def evaluate_safety(self, tool_name: str, command: str, **kwargs: object) -> tuple[str, str | None]:
        """Legacy method - use evaluate() instead."""
        return self._check_command_safety(command)

    def should_prompt_user(self, tool_name: str, tool_input: dict[str, object]) -> tuple[bool, str | None]:
        """Legacy method - use evaluate() instead."""
        command = tool_input.get("command", "")
        command_str = str(command) if command else ""
        decision, reason = self._check_command_safety(command_str)
        return (decision == "ask", reason) if decision == "ask" else (False, reason if decision == "deny" else None)

    def check_safety(self, tool_name: str, command: str) -> str:
        """Legacy method - use evaluate() instead. Returns 'allow', 'ask', or 'deny'."""
        decision, _ = self._check_command_safety(command)
        return decision

    def pre_tool_use_decision(self, tool_name: str, tool_input: dict[str, object]) -> DecisionResult:
        """Make decision for pre tool use hook."""
        if not tool_input or not tool_input.get("command"):
            return DecisionResult("allow", "No command to evaluate", blocked=False)

        command = tool_input.get("command", "")
        command_str = str(command) if command else ""
        decision, reason = self._check_command_safety(command_str)

        if decision == "deny":
            return DecisionResult("deny", reason or "Dangerous command detected", blocked=True)
        if decision == "ask":
            return DecisionResult("ask", reason or "Command requires confirmation", blocked=False)
        return DecisionResult("allow", "Command is safe", blocked=False)

    def post_tool_use_decision(self, tool_name: str, result: dict[str, object]) -> DecisionResult:
        """Make decision for post tool use hook - typically allows continuation."""
        # PostToolUse typically doesn't block, just audits and alerts
        # Only block if there's a critical error that needs attention
        success = result.get("success")
        exit_code = result.get("exitCode") or result.get("exit_code")

        # Most failures just trigger alerts, not blocks
        if success is False or (isinstance(exit_code, int) and exit_code != 0):
            return DecisionResult("allow", "Tool execution failed but continuing", blocked=False)

        return DecisionResult("allow", "Tool executed successfully", blocked=False)


class DecisionResult:
    """Simple decision result container."""

    def __init__(self, decision: str, reason: str, blocked: bool = False, **kwargs: object) -> None:
        self.decision = decision
        self.reason = reason
        self.blocked = blocked
        self.additional_context: dict[str, object] = dict(kwargs)
        # Set up payload for backward compatibility
        self.payload: dict[str, object] = {
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
            "decision": decision,
            "continue": not blocked,
            "additionalContext": self.additional_context,
        }

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary format."""
        return {
            "decision": self.decision,
            "reason": self.reason,
            "blocked": self.blocked,
            "permissionDecision": self.decision,
            "permissionDecisionReason": self.reason,
            "continue": not self.blocked,
            "additionalContext": self.payload.get("additionalContext", self.additional_context),
        }