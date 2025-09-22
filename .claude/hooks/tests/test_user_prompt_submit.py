#!/usr/bin/env python3
"""UserPromptSubmit hook focused tests."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_ROOT = REPO_ROOT / ".claude" / "hooks"
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

import user_prompt_submit as hook_module


class TestUserPromptSubmitHook(unittest.TestCase):
    """Covers prompt sanitisation, abuse detection, and rate limiting."""

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory(prefix="prompt-submit-tests-")
        self.addCleanup(self._tempdir.cleanup)
        tmp_path = Path(self._tempdir.name)
        self.prompt_log = tmp_path / "prompt_submissions.jsonl"
        self.rate_log = tmp_path / "prompt_rates.json"

        self._patchers = [
            patch("user_prompt_submit.PROMPT_LOG_PATH", self.prompt_log),
            patch("user_prompt_submit.RATE_LIMIT_PATH", self.rate_log),
        ]
        for patcher in self._patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    # Helpers -----------------------------------------------------------
    def _execute(self, payload: dict, *, time_value: float | None = None):
        hook = hook_module.UserPromptSubmitHook()
        if time_value is None:
            return hook.execute(payload, enable_audio=False)
        with patch("user_prompt_submit.time.time", return_value=time_value):
            return hook.execute(payload, enable_audio=False)

    @staticmethod
    def _decode_context(result: hook_module.HookExecutionResult) -> dict:
        payload = result.payload["hookSpecificOutput"]["additionalContext"]
        return json.loads(payload)

    # Tests -------------------------------------------------------------
    def test_normal_prompt_passes_validation(self) -> None:
        payload = {
            "prompt": "print('hello world')",
            "user_id": "user-123",
            "session_id": "session-abc",
            "metadata": {"language": "python"},
        }

        result = self._execute(payload)
        context = self._decode_context(result)

        self.assertTrue(result.continue_value)
        self.assertNotIn("decision", result.payload)
        self.assertEqual(context["promptPreview"], "print('hello world')")
        self.assertEqual(context["length"], len(payload["prompt"]))
        self.assertEqual(context.get("issues"), [])
        # Log file should contain the submission summary with same user/session IDs
        log_lines = self.prompt_log.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(log_lines), 1)
        logged = json.loads(log_lines[0])
        self.assertEqual(logged["userId"], "user-123")
        self.assertEqual(logged["sessionId"], "session-abc")
        self.assertFalse(logged["issues"])

    def test_suspicious_prompt_triggers_block(self) -> None:
        payload = {"prompt": "DROP TABLE users;", "user_id": "user-007"}

        result = self._execute(payload)
        context = self._decode_context(result)

        self.assertFalse(result.continue_value)
        self.assertEqual(result.payload["decision"], "block")
        self.assertIn("sql_drop", context["issues"])
        self.assertIn("Issues detected", result.payload["reason"])

    def test_rate_limiting_detects_quick_repeats(self) -> None:
        payload = {"prompt": "run diagnostics", "session_id": "sess-1"}

        # First submission establishes the rate tracker entry
        self._execute(payload, time_value=1000.0)
        # Second submission happens immediately afterwards -> should be blocked
        result = self._execute(payload, time_value=1000.2)
        context = self._decode_context(result)

        self.assertFalse(result.continue_value)
        self.assertEqual(result.payload["decision"], "block")
        self.assertIn("rate_limited", context["issues"])
        self.assertIn("rate limited", result.payload["reason"])

    def test_prompt_truncation_marks_issue_and_limits_length(self) -> None:
        original = "a" * (hook_module.MAX_PROMPT_LENGTH + 128)
        payload = {"prompt": original, "session_id": "sess-2"}

        result = self._execute(payload)
        context = self._decode_context(result)

        self.assertFalse(result.continue_value)
        self.assertEqual(result.payload["decision"], "block")
        self.assertEqual(context["length"], hook_module.MAX_PROMPT_LENGTH)
        self.assertIn("prompt_truncated", context["issues"])
        self.assertLessEqual(len(context["promptPreview"]), hook_module.MAX_PREVIEW)


if __name__ == "__main__":  # pragma: no cover - script compatibility
    unittest.main()
