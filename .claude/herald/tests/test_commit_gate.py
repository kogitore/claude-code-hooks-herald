#!/usr/bin/env python3
"""Tests for Block-at-Commit Strategy in PreToolUse hook."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_DIR = REPO_ROOT / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from herald.handlers.pre_tool_use import _check_commit_gate, COMMIT_GATE_FILE


class TestCommitGate(unittest.TestCase):
    """Tests for commit gate functionality (Block-at-Commit strategy)."""

    def test_non_bash_tool_always_allowed(self) -> None:
        """Non-Bash tools should always be allowed."""
        allowed, reason = _check_commit_gate("Read", "anything")
        self.assertTrue(allowed)
        self.assertIsNone(reason)

        allowed, reason = _check_commit_gate("Write", "anything")
        self.assertTrue(allowed)
        self.assertIsNone(reason)

        allowed, reason = _check_commit_gate("Edit", "anything")
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_bash_without_git_commit_allowed(self) -> None:
        """Bash commands without git commit should be allowed."""
        commands = [
            "ls -la",
            "git status",
            "git diff",
            "git add .",
            "npm install",
            "pytest tests/",
        ]
        for cmd in commands:
            with self.subTest(command=cmd):
                allowed, reason = _check_commit_gate("Bash", cmd)
                self.assertTrue(allowed, f"Command should be allowed: {cmd}")
                self.assertIsNone(reason)

    def test_git_commit_blocked_without_gate_file(self) -> None:
        """git commit should be blocked when gate file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_gate = Path(tmpdir) / "nonexistent"
            with patch("herald.handlers.pre_tool_use.COMMIT_GATE_FILE", fake_gate):
                with patch.dict(os.environ, {"HOOKS_SKIP_COMMIT_GATE": ""}):
                    allowed, reason = _check_commit_gate("Bash", "git commit -m 'test'")
                    self.assertFalse(allowed)
                    self.assertIn("run tests first", reason)

    def test_git_commit_allowed_with_gate_file(self) -> None:
        """git commit should be allowed when gate file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gate_file = Path(tmpdir) / "tests-pass"
            gate_file.touch()  # Create the gate file
            with patch("herald.handlers.pre_tool_use.COMMIT_GATE_FILE", gate_file):
                allowed, reason = _check_commit_gate("Bash", "git commit -m 'test'")
                self.assertTrue(allowed)
                self.assertIsNone(reason)

    def test_git_commit_allowed_with_skip_env_var(self) -> None:
        """git commit should be allowed when HOOKS_SKIP_COMMIT_GATE is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_gate = Path(tmpdir) / "nonexistent"
            with patch("herald.handlers.pre_tool_use.COMMIT_GATE_FILE", fake_gate):
                for val in ("1", "true", "yes", "TRUE", "Yes"):
                    with self.subTest(env_value=val):
                        with patch.dict(os.environ, {"HOOKS_SKIP_COMMIT_GATE": val}):
                            allowed, reason = _check_commit_gate("Bash", "git commit -m 'test'")
                            self.assertTrue(allowed, f"Should be allowed with HOOKS_SKIP_COMMIT_GATE={val}")

    def test_various_git_commit_patterns(self) -> None:
        """Various git commit command patterns should be detected."""
        commands = [
            "git commit -m 'message'",
            'git commit -m "message"',
            "git commit --amend",
            "git commit -a -m 'message'",
            "GIT_AUTHOR_DATE=2020-01-01 git commit -m 'test'",
            "git commit",
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_gate = Path(tmpdir) / "nonexistent"
            with patch("herald.handlers.pre_tool_use.COMMIT_GATE_FILE", fake_gate):
                with patch.dict(os.environ, {"HOOKS_SKIP_COMMIT_GATE": ""}):
                    for cmd in commands:
                        with self.subTest(command=cmd):
                            allowed, reason = _check_commit_gate("Bash", cmd)
                            self.assertFalse(allowed, f"Should block git commit: {cmd}")


class TestCommitGateIntegration(unittest.TestCase):
    """Integration tests for commit gate in PreToolUse handler."""

    def _dispatch(self, payload: dict) -> object:
        """Dispatch a pre tool use event."""
        disp = build_default_dispatcher()  # noqa: F821 - injected by conftest
        return disp.dispatch("PreToolUse", payload=payload)

    def test_handler_blocks_git_commit_without_gate(self) -> None:
        """Handler should block git commit when gate file is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_gate = Path(tmpdir) / "nonexistent"
            with patch("herald.handlers.pre_tool_use.COMMIT_GATE_FILE", fake_gate):
                with patch.dict(os.environ, {"HOOKS_SKIP_COMMIT_GATE": ""}):
                    payload = {
                        "tool": "Bash",
                        "toolInput": {"command": "git commit -m 'test'"},
                    }
                    report = self._dispatch(payload)
                    hso = report.response.get("hookSpecificOutput", {})
                    # Should block (ask for confirmation)
                    self.assertEqual(hso.get("permissionDecision"), "ask")
                    self.assertFalse(report.response.get("continue", True))

    def test_handler_allows_git_commit_with_gate(self) -> None:
        """Handler should allow git commit when gate file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gate_file = Path(tmpdir) / "tests-pass"
            gate_file.touch()  # Create the gate file
            with patch("herald.handlers.pre_tool_use.COMMIT_GATE_FILE", gate_file):
                payload = {
                    "tool": "Bash",
                    "toolInput": {"command": "git commit -m 'test'"},
                }
                report = self._dispatch(payload)
                hso = report.response.get("hookSpecificOutput", {})
                # Should allow
                self.assertEqual(hso.get("permissionDecision"), "allow")
                self.assertTrue(report.response.get("continue", False))

    def test_handler_allows_non_commit_commands(self) -> None:
        """Handler should allow non-commit git commands without gate file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_gate = Path(tmpdir) / "nonexistent"
            with patch("herald.handlers.pre_tool_use.COMMIT_GATE_FILE", fake_gate):
                with patch.dict(os.environ, {"HOOKS_SKIP_COMMIT_GATE": ""}):
                    for cmd in ["git status", "git diff", "git add ."]:
                        with self.subTest(command=cmd):
                            payload = {
                                "tool": "Bash",
                                "toolInput": {"command": cmd},
                            }
                            report = self._dispatch(payload)
                            hso = report.response.get("hookSpecificOutput", {})
                            # Should allow
                            self.assertEqual(hso.get("permissionDecision"), "allow")
                            self.assertTrue(report.response.get("continue", False))


if __name__ == "__main__":
    unittest.main()
