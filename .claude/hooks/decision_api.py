#!/usr/bin/env python3
"""
Decision API for Claude Code Hooks Herald

This module provides intelligent decision-making capabilities for
PreToolUse, PostToolUse, and Stop hooks in the Herald system.
"""

import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path


class DecisionAPI:
    """Intelligent decision-making API for Claude Code hooks."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Decision API."""
        self.config = config or {}
        self.logger = self._setup_logging()

        # Load rule sets
        self.dangerous_commands = self._load_dangerous_commands()
        self.protected_files = self._load_protected_files()
        self.auto_format_rules = self._load_auto_format_rules()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the decision API."""
        logger = logging.getLogger("decision_api")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _load_dangerous_commands(self) -> List[str]:
        """Load patterns for dangerous commands."""
        return [
            r'rm\s+-rf\s+/',           # Delete root
            r'chmod\s+777',            # Dangerous permissions
            r'>\s*/dev/sd[a-z]',       # Direct disk writes
            r':\(\)\{\s*:\|\:&\s*\}\s*;:', # Fork bomb
            r'dd\s+if=/dev/[^/]+\s+of=', # Disk operations
            r'mkfs\.',                 # Format filesystem
            r'fdisk',                  # Partition operations
            r'sudo\s+rm\s+-rf',       # Sudo + dangerous rm
            r'curl\s+.*\|\s*bash',     # Pipe to bash
            r'wget\s+.*\|\s*sh',       # Pipe to shell
            r'eval\s+.*\$\(',          # Dangerous eval
        ]

    def _load_protected_files(self) -> List[str]:
        """Load patterns for protected files."""
        return [
            r'\.env.*',                # Environment files
            r'.*\.key$',               # Key files
            r'.*\.pem$',               # Certificate files
            r'credentials\.json',      # Credentials
            r'\.git/config',           # Git config
            r'\.ssh/.*',               # SSH files
            r'.*password.*',           # Password files
            r'.*secret.*',             # Secret files
            r'\.aws/credentials',      # AWS credentials
            r'\.docker/config\.json',  # Docker config
        ]

    def _load_auto_format_rules(self) -> Dict[str, str]:
        """Load auto-formatting rules."""
        return {
            "*.py": "black --quiet",
            "*.js": "prettier --write",
            "*.ts": "prettier --write",
            "*.jsx": "prettier --write",
            "*.tsx": "prettier --write",
            "*.json": "prettier --write",
            "*.md": "prettier --write",
            "*.yaml": "prettier --write",
            "*.yml": "prettier --write",
            "*.css": "prettier --write",
            "*.scss": "prettier --write",
            "*.html": "prettier --write",
        }

    def pre_tool_use_decision(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a decision for PreToolUse events.

        Args:
            tool_name: Name of the tool being used
            tool_input: Input parameters for the tool

        Returns:
            Dictionary with permission decision and reasoning
        """
        try:
            decision_start = time.time()

            # Check for dangerous operations
            if tool_name.lower() in ["bash", "shell", "exec"]:
                command = tool_input.get("command", "")
                danger_result = self._check_dangerous_command(command)
                if danger_result["is_dangerous"]:
                    return {
                        "permissionDecision": "deny",
                        "reason": danger_result["reason"],
                        "tool_name": tool_name,
                        "risk_level": "high",
                        "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
                    }

            # Check for protected file access
            if tool_name.lower() in ["write", "edit", "delete", "remove"]:
                file_path = tool_input.get("file_path", "")
                protection_result = self._check_protected_file(file_path)
                if protection_result["is_protected"]:
                    return {
                        "permissionDecision": "ask",
                        "reason": protection_result["reason"],
                        "tool_name": tool_name,
                        "risk_level": "medium",
                        "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
                    }

            # Default: allow with logging
            self.logger.info(f"Allowing tool use: {tool_name}")
            return {
                "permissionDecision": "allow",
                "reason": "No security concerns detected",
                "tool_name": tool_name,
                "risk_level": "low",
                "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
            }

        except Exception as e:
            self.logger.error(f"Error in pre_tool_use_decision: {e}")
            return {
                "permissionDecision": "ask",
                "reason": f"Decision error: {str(e)}",
                "tool_name": tool_name,
                "risk_level": "unknown"
            }

    def _check_dangerous_command(self, command: str) -> Dict[str, Any]:
        """Check if a command is dangerous."""
        for pattern in self.dangerous_commands:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    "is_dangerous": True,
                    "reason": f"Command matches dangerous pattern: {pattern}",
                    "matched_pattern": pattern
                }

        return {
            "is_dangerous": False,
            "reason": "Command appears safe"
        }

    def _check_protected_file(self, file_path: str) -> Dict[str, Any]:
        """Check if a file is protected."""
        for pattern in self.protected_files:
            if re.search(pattern, file_path, re.IGNORECASE):
                return {
                    "is_protected": True,
                    "reason": f"File matches protected pattern: {pattern}",
                    "matched_pattern": pattern
                }

        return {
            "is_protected": False,
            "reason": "File not protected"
        }

    def post_tool_use_decision(self, tool_name: str, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a decision for PostToolUse events.

        Args:
            tool_name: Name of the tool that was used
            tool_result: Result of the tool execution

        Returns:
            Dictionary with post-processing decision and actions
        """
        try:
            decision_start = time.time()

            # Check if tool execution was successful
            if tool_result.get("error"):
                return {
                    "decision": "log_error",
                    "reason": f"Tool execution failed: {tool_result['error']}",
                    "tool_name": tool_name,
                    "actions": ["log", "notify"],
                    "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
                }

            # Auto-format files if applicable
            if tool_name.lower() in ["write", "edit"] and "file_path" in tool_result:
                file_path = tool_result["file_path"]
                format_action = self._get_format_action(file_path)
                if format_action:
                    return {
                        "decision": "auto_format",
                        "reason": f"Auto-formatting {Path(file_path).suffix} file",
                        "tool_name": tool_name,
                        "actions": ["format", "log"],
                        "format_command": format_action,
                        "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
                    }

            # Default: log successful execution
            return {
                "decision": "log_success",
                "reason": "Tool executed successfully",
                "tool_name": tool_name,
                "actions": ["log"],
                "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
            }

        except Exception as e:
            self.logger.error(f"Error in post_tool_use_decision: {e}")
            return {
                "decision": "log_error",
                "reason": f"Decision error: {str(e)}",
                "tool_name": tool_name,
                "actions": ["log"]
            }

    def _get_format_action(self, file_path: str) -> Optional[str]:
        """Get the formatting command for a file."""
        file_path_obj = Path(file_path)

        for pattern, command in self.auto_format_rules.items():
            if file_path_obj.match(pattern):
                return command.replace("{file}", file_path)

        return None

    def stop_decision(self, transcript: Dict[str, Any], stop_count: int = 0) -> Dict[str, Any]:
        """
        Make a decision for Stop events.

        Args:
            transcript: The conversation transcript
            stop_count: Number of times stop has been called

        Returns:
            Dictionary with stop decision and reasoning
        """
        try:
            decision_start = time.time()

            # Prevent infinite loops
            max_stops = self.config.get("max_stop_count", 3)
            if stop_count >= max_stops:
                return {
                    "decision": "block",
                    "reason": f"Maximum stop count ({max_stops}) exceeded",
                    "stop_count": stop_count,
                    "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
                }

            # Check if transcript indicates active hooks
            transcript_content = str(transcript).lower()
            if "stop_hook_active" in transcript_content:
                return {
                    "decision": "block",
                    "reason": "Stop hook already active",
                    "stop_count": stop_count,
                    "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
                }

            # Check for completion indicators
            completion_result = self._analyze_completion(transcript)

            if completion_result["needs_continuation"]:
                return {
                    "decision": "continue",
                    "reason": completion_result["reason"],
                    "stop_count": stop_count,
                    "indicators": completion_result["indicators"],
                    "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
                }

            # Default: allow stop
            return {
                "decision": "allow",
                "reason": "Task appears complete",
                "stop_count": stop_count,
                "decision_time_ms": round((time.time() - decision_start) * 1000, 2)
            }

        except Exception as e:
            self.logger.error(f"Error in stop_decision: {e}")
            return {
                "decision": "allow",  # Safe default
                "reason": f"Decision error: {str(e)}",
                "stop_count": stop_count
            }

    def _analyze_completion(self, transcript: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze if the task needs continuation."""
        content = str(transcript).lower()

        # Indicators that suggest more work is needed
        incomplete_indicators = [
            "todo",
            "fixme",
            "error",
            "failed",
            "incomplete",
            "pending",
            "not implemented",
            "coming soon",
            "placeholder",
        ]

        # Indicators that suggest completion
        complete_indicators = [
            "done",
            "completed",
            "finished",
            "success",
            "ready",
            "deployed",
            "tested",
        ]

        found_incomplete = []
        found_complete = []

        for indicator in incomplete_indicators:
            if indicator in content:
                found_incomplete.append(indicator)

        for indicator in complete_indicators:
            if indicator in content:
                found_complete.append(indicator)

        # Simple scoring system
        incomplete_score = len(found_incomplete)
        complete_score = len(found_complete)

        if incomplete_score > complete_score:
            return {
                "needs_continuation": True,
                "reason": f"Found {incomplete_score} incomplete indicators",
                "indicators": found_incomplete
            }

        return {
            "needs_continuation": False,
            "reason": f"Task appears complete (score: {complete_score} vs {incomplete_score})",
            "indicators": found_complete
        }


def main():
    """Test the Decision API."""
    api = DecisionAPI()

    # Test dangerous command detection
    result = api.pre_tool_use_decision("bash", {"command": "rm -rf /"})
    print(f"Dangerous command result: {result}")

    # Test safe command
    result = api.pre_tool_use_decision("bash", {"command": "ls -la"})
    print(f"Safe command result: {result}")

    # Test protected file
    result = api.pre_tool_use_decision("write", {"file_path": ".env"})
    print(f"Protected file result: {result}")

    # Test stop decision
    result = api.stop_decision({"content": "Task completed successfully"})
    print(f"Stop decision result: {result}")


if __name__ == "__main__":
    main()