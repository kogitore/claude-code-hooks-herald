#!/usr/bin/env python3
"""PostToolUse hook regression tests."""
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

from herald import HANDLERS
from utils import constants


class TestPostToolUseHook(unittest.TestCase):
    """Exercises success and failure decision paths."""

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory(prefix="post-tool-tests-")
        self.addCleanup(self._tempdir.cleanup)
        self.audit_path = Path(self._tempdir.name) / "tool_audit.jsonl"
        patcher = patch("post_tool_use.AUDIT_LOG_PATH", self.audit_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _dispatch(self, payload: dict):
        disp = build_default_dispatcher()
        return disp.dispatch(constants.POST_TOOL_USE, payload=payload)

    @staticmethod
    def _decode_context(report) -> dict:
        data = report.response.get("hookSpecificOutput", {}).get("additionalContext", "{}")
        return json.loads(data or "{}")

    def test_successful_result_is_logged_and_allows_flow(self) -> None:
        payload = {
            "tool": "bash",
            "result": {
                "success": True,
                "output": "operation complete",
                "exitCode": 0,
            },
            "execution_time": 0.42,
        }
        report = self._dispatch(payload)
        context = self._decode_context(report)

        self.assertTrue(report.response.get("continue", False))
        self.assertNotIn("decision", report.response)
        self.assertEqual(context["tool"], "bash")
        self.assertEqual(context["result"]["success"], True)
        self.assertIn("outputPreview", context["result"])
        self.assertFalse(context["shouldAlert"])

        lines = self.audit_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        logged = json.loads(lines[0])
        self.assertEqual(logged["tool"], "bash")
        self.assertEqual(logged["decision"], "allow")

    def test_error_result_blocks_and_marks_alerts(self) -> None:
        payload = {
            "tool": "python",
            "result": {
                "success": False,
                "error": "Traceback...",
                "exit_code": 2,
            },
        }

        report = self._dispatch(payload)
        context = self._decode_context(report)

        self.assertFalse(report.response.get("continue", True))
        self.assertEqual(report.response.get("decision"), "block")
        alerts = context["result"].get("alerts", [])
        self.assertIn("decision_blocked", alerts)
        self.assertIn("error_detected", alerts)
        self.assertTrue(context["shouldAlert"])

        lines = self.audit_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        logged = json.loads(lines[0])
        self.assertEqual(logged["decision"], "block")
        self.assertEqual(logged["shouldAlert"], True)

    def test_long_output_is_truncated_in_context(self) -> None:
        # match module-level constant
        long_output = "x" * (600 + 200)
        payload = {
            "tool": "bash",
            "result": {"success": True, "output": long_output},
        }

        report = self._dispatch(payload)
        context = self._decode_context(report)
        snippet = context["result"].get("outputPreview", "")

        self.assertTrue(report.response.get("continue", False))
        self.assertEqual(len(snippet), 600)
        self.assertTrue(context["result"].get("outputTruncated"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
