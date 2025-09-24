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

from herald import build_default_dispatcher
from utils import constants


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
    def _dispatch(self, payload: dict, *, time_value: float | None = None):
        disp = build_default_dispatcher()
        if time_value is None:
            return disp.dispatch(constants.USER_PROMPT_SUBMIT, payload=payload)
        with patch("user_prompt_submit.time.time", return_value=time_value):
            return disp.dispatch(constants.USER_PROMPT_SUBMIT, payload=payload)

    @staticmethod
    def _decode_context(report) -> dict:
        payload = report.response.get("hookSpecificOutput", {}).get("additionalContext", "{}")
        return json.loads(payload or "{}")

    # Tests -------------------------------------------------------------
    def test_normal_prompt_passes_validation(self) -> None:
        payload = {
            "prompt": "print('hello world')",
            "user_id": "user-123",
            "session_id": "session-abc",
            "metadata": {"language": "python"},
        }
        report = self._dispatch(payload)
        context = self._decode_context(report)

        self.assertTrue(report.response.get("continue", False))
        self.assertNotIn("decision", report.response)
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

        report = self._dispatch(payload)
        context = self._decode_context(report)

        self.assertFalse(report.response.get("continue", True))
        self.assertEqual(report.response.get("decision"), "block")
        self.assertIn("sql_drop", context["issues"])
        self.assertIn("Issues detected", report.response.get("reason", ""))

    def test_rate_limiting_detects_quick_repeats(self) -> None:
        payload = {"prompt": "run diagnostics", "session_id": "sess-1"}

        # First submission establishes the rate tracker entry
        self._dispatch(payload, time_value=1000.0)
        # Second submission happens immediately afterwards -> should be blocked
        report = self._dispatch(payload, time_value=1000.2)
        context = self._decode_context(report)

        self.assertFalse(report.response.get("continue", True))
        self.assertEqual(report.response.get("decision"), "block")
        self.assertIn("rate_limited", context["issues"])
        self.assertIn("rate limited", report.response.get("reason", ""))

    def test_prompt_truncation_marks_issue_and_limits_length(self) -> None:
        original = "a" * (4000 + 128)
        payload = {"prompt": original, "session_id": "sess-2"}

        report = self._dispatch(payload)
        context = self._decode_context(report)

        self.assertFalse(report.response.get("continue", True))
        self.assertEqual(report.response.get("decision"), "block")
        self.assertEqual(context["length"], 4000)
        self.assertIn("prompt_truncated", context["issues"])
        self.assertLessEqual(len(context["promptPreview"]), 240)


if __name__ == "__main__":  # pragma: no cover - script compatibility
    unittest.main()
