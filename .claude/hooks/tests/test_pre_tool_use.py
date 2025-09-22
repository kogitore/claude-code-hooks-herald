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

import pre_tool_use as hook_module


class TestPreToolUseHook(unittest.TestCase):
    """Validates tool extraction, decision policy integration, and fallbacks."""

    def _execute(self, payload: dict, hook: hook_module.PreToolUseHook | None = None):
        hook = hook or hook_module.PreToolUseHook()
        return hook.execute(payload, enable_audio=False)

    def test_safe_command_allows_execution(self) -> None:
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
        }

        result = self._execute(payload)

        self.assertTrue(result.continue_value)
        self.assertEqual(result.payload["permissionDecision"], "allow")
        audit = result.payload["preToolUseAudit"]
        self.assertEqual(audit["decision"], "allow")
        self.assertEqual(audit["blocked"], False)

    def test_dangerous_command_is_denied(self) -> None:
        payload = {
            "tool": "bash",
            "toolInput": {"command": "rm -rf /"},
        }

        result = self._execute(payload)

        self.assertFalse(result.continue_value)
        self.assertEqual(result.payload["permissionDecision"], "deny")
        self.assertIn("rm -rf /", result.payload["preToolUseAudit"].get("commandPreview", ""))

    def test_invalid_tool_input_promotes_manual_review(self) -> None:
        payload = {
            "tool": "bash",
            "tool_input": "{not-json",
        }

        result = self._execute(payload)

        self.assertFalse(result.continue_value)
        self.assertEqual(result.payload["permissionDecision"], "ask")
        issues = result.payload.get("additionalContext", {}).get("issues", [])
        self.assertIn("invalid_tool_input_json", issues)

    def test_decision_api_failure_falls_back_to_ask(self) -> None:
        hook = hook_module.PreToolUseHook()
        with patch.object(hook._decision_api, "pre_tool_use_decision", side_effect=RuntimeError("boom")):
            result = self._execute({"tool": "bash"}, hook=hook)

        self.assertFalse(result.continue_value)
        self.assertEqual(result.payload["permissionDecision"], "ask")
        self.assertEqual(result.payload["preToolUseAudit"]["blocked"], True)
        self.assertIn("請人工確認", result.payload.get("permissionDecisionReason", ""))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
