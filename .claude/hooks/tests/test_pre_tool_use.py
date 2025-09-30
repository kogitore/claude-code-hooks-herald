#!/usr/bin/env python3
"""PreToolUse hook decision-path tests."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_ROOT = REPO_ROOT / ".claude" / "hooks"
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from herald import dispatch
from utils import constants


class TestPreToolUseHook(unittest.TestCase):
    """Validates tool extraction, decision policy integration, and fallbacks."""

    def _dispatch(self, payload: dict):
        return dispatch(constants.PRE_TOOL_USE, payload=payload)

    def test_safe_command_allows_execution(self) -> None:
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
        }
        report = self._dispatch(payload)
        self.assertTrue(report.get("continue", False))
        hso = report.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("hookEventName"), constants.PRE_TOOL_USE)
        self.assertEqual(hso.get("permissionDecision"), "allow")

    def test_dangerous_command_is_denied(self) -> None:
        payload = {
            "tool": "bash",
            "toolInput": {"command": "rm -rf /"},
        }
        report = self._dispatch(payload)
        self.assertFalse(report.get("continue", True))
        hso = report.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("permissionDecision"), "deny")

    def test_invalid_tool_input_promotes_manual_review(self) -> None:
        payload = {
            "tool": "bash",
            "tool_input": "{not-json",
        }
        report = self._dispatch(payload)
        self.assertFalse(report.get("continue", True))
        hso = report.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("permissionDecision"), "ask")

    def test_decision_api_failure_falls_back_to_ask(self) -> None:
        # Patch DecisionAPI via module to simulate failure
        import utils.decision_api as dec
        with patch.object(dec.DecisionAPI, "pre_tool_use_decision", side_effect=RuntimeError("boom")):
            report = self._dispatch({"tool": "bash"})
        self.assertFalse(report.get("continue", True))
        hso = report.get("hookSpecificOutput", {})
        self.assertEqual(hso.get("permissionDecision"), "ask")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
