#!/usr/bin/env python3
"""Session lifecycle hook tests."""
from __future__ import annotations

import json
import os
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
import utils.session_storage as session_storage


class SessionManagementTestCase(unittest.TestCase):
    """Validates session start/end hooks integration with session storage."""

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory(prefix="session-management-tests-")
        self.addCleanup(self._tempdir.cleanup)

        tmp_root = Path(self._tempdir.name)
        self.logs_root = tmp_root / "logs"
        self.sessions_root = tmp_root / "sessions"
        self.logs_root.mkdir(parents=True, exist_ok=True)
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self.sessions_root_resolved = self.sessions_root.resolve()

        self.state_path = self.logs_root / "session_state.json"
        self.events_path = self.logs_root / "session_events.jsonl"

        # Redirect session storage paths
        patchers = [
            patch("utils.session_storage._LOGS_ROOT", self.logs_root),
            patch("utils.session_storage.STATE_PATH", self.state_path),
            patch("utils.session_storage.EVENT_LOG_PATH", self.events_path),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        # Ensure hooks create directories inside our temporary fixture
        self.start_root_patch = patch(
            "session_start._session_root_path",
            lambda sid: self.sessions_root_resolved / sid,
        )
        self.end_root_patch = patch(
            "session_end._session_root_path",
            lambda sid: self.sessions_root_resolved / sid,
        )
        self.start_root_patch.start()
        self.end_root_patch.start()
        self.addCleanup(self.start_root_patch.stop)
        self.addCleanup(self.end_root_patch.stop)

        # Stabilize health checks to avoid environment flakiness
        self.checks_patch = patch(
            "session_start._run_health_checks",
            return_value=(("working_directory_exists",), ()),
        )
        self.checks_patch.start()
        self.addCleanup(self.checks_patch.stop)

        os.environ["CLAUDE_SESSION_ROOT"] = str(self.sessions_root)
        self.addCleanup(os.environ.pop, "CLAUDE_SESSION_ROOT", None)

    # Helpers -----------------------------------------------------------
    def _start_session(self, payload: dict = None):
        payload = payload or {
            "session_id": "sess-test",
            "user_id": "user-1",
            "start_time": "2025-09-22T00:00:00Z",
            "environment": {"working_directory": str(self.logs_root)},
            "preferences": {"audio_enabled": True},
        }
        disp = build_default_dispatcher()
        return disp.dispatch(constants.SESSION_START, payload=payload)

    def _end_session(self, payload: dict = None):
        payload = payload or {
            "session_id": "sess-test",
            "end_time": "2025-09-22T01:00:00Z",
            "duration": 3600,
            "termination_reason": "normal",
            "resources_to_cleanup": ["tmp"],
        }
        disp = build_default_dispatcher()
        return disp.dispatch(constants.SESSION_END, payload=payload)

    @staticmethod
    def _decode_context(report) -> dict:
        raw = report.response.get("hookSpecificOutput", {}).get("additionalContext", "{}")
        return json.loads(raw or "{}")

    # Tests -------------------------------------------------------------
    def test_session_start_writes_state_and_event_log(self) -> None:
        report = self._start_session()
        context = self._decode_context(report)

        self.assertTrue(report.response.get("continue", False))
        self.assertEqual(context["sessionId"], "sess-test")
        self.assertIn("workspace", context)
        self.assertPathExists(self.sessions_root_resolved / "sess-test")

        state = session_storage.load_state()
        self.assertIn("sess-test", state)
        history = state["sess-test"].get("history", [])
        self.assertEqual(history[0]["event"], "session_start")

        events = self.events_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(events), 1)
        self.assertEqual(json.loads(events[0])["event"], "session_start")

    def test_session_end_updates_state_and_removes_resources(self) -> None:
        # Seed state with an active session entry
        session_storage.write_state({"sess-test": {"state": {"status": "active"}, "history": []}})
        target_dir = (self.sessions_root / "sess-test" / "tmp")
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "artifact.txt").write_text("temp", encoding="utf-8")

        report = self._end_session()
        context = self._decode_context(report)

        self.assertTrue(report.response.get("continue", False))
        self.assertIn("sess-test", context["removedResources"][0])
        self.assertFalse(target_dir.exists())

        state = session_storage.load_state()["sess-test"]
        self.assertEqual(state["state"]["status"], "ended")
        self.assertEqual(state["history"][-1]["event"], "session_end")

        events = self.events_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(events), 1)
        self.assertEqual(json.loads(events[0])["event"], "session_end")

    def test_full_lifecycle_records_start_and_end(self) -> None:
        self._start_session()
        self._end_session()

        state = session_storage.load_state()["sess-test"]
        history_events = [entry["event"] for entry in state["history"]]
        self.assertEqual(history_events, ["session_start", "session_end"])

        events = self.events_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(events), 2)
        self.assertEqual(
            [json.loads(line)["event"] for line in events],
            ["session_start", "session_end"],
        )

    # Utility -----------------------------------------------------------
    def assertPathExists(self, path: Path) -> None:  # noqa: N802
        self.assertTrue(path.exists(), f"Expected path to exist: {path}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
