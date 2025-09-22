#!/usr/bin/env python3
"""Unit tests for ``utils.session_storage``."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the hooks directory is importable when this file is executed as a script
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_ROOT = REPO_ROOT / ".claude" / "hooks"
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

import utils.session_storage as session_storage


class TestSessionStorage(unittest.TestCase):
    """Behavioural tests for session state persistence helpers."""

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory(prefix="session-storage-tests-")
        self.addCleanup(self._tempdir.cleanup)
        self.logs_root = Path(self._tempdir.name)
        self.state_path = self.logs_root / "session_state.json"
        self.event_path = self.logs_root / "session_events.jsonl"

        # Redirect module-level paths to the temporary fixture directory
        self._patchers = [
            patch("utils.session_storage._LOGS_ROOT", self.logs_root),
            patch("utils.session_storage.STATE_PATH", self.state_path),
            patch("utils.session_storage.EVENT_LOG_PATH", self.event_path),
        ]
        for patcher in self._patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    # -- load_state -----------------------------------------------------
    def test_load_state_returns_dict_when_file_exists(self) -> None:
        sample = {"session-1": {"state": {"status": "active"}}}
        self.state_path.write_text(json.dumps(sample), encoding="utf-8")

        loaded = session_storage.load_state()

        self.assertEqual(loaded, sample)

    def test_load_state_returns_empty_when_missing(self) -> None:
        self.assertFalse(self.state_path.exists())
        self.assertEqual(session_storage.load_state(), {})

    def test_load_state_handles_invalid_json(self) -> None:
        self.state_path.write_text("{not-json", encoding="utf-8")
        self.assertEqual(session_storage.load_state(), {})

    def test_load_state_non_mapping_defaults_to_empty(self) -> None:
        self.state_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        self.assertEqual(session_storage.load_state(), {})

    # -- write_state ----------------------------------------------------
    def test_write_state_persists_json_payload(self) -> None:
        payload = {"session-2": {"state": {"status": "ended"}}}
        session_storage.write_state(payload)

        self.assertTrue(self.state_path.exists())
        on_disk = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, payload)

    def test_write_state_swallows_permission_errors(self) -> None:
        with patch("pathlib.Path.write_text", side_effect=OSError("denied")) as mocked_write:
            session_storage.write_state({"demo": {}})
        self.assertTrue(mocked_write.called)
        self.assertFalse(self.state_path.exists())

    # -- append_event_log -----------------------------------------------
    def test_append_event_log_appends_newline_delimited_json(self) -> None:
        records = [
            {"event": "session_start", "sessionId": "s-1"},
            {"event": "session_end", "sessionId": "s-1", "status": "ok"},
        ]
        for rec in records:
            session_storage.append_event_log(rec)

        lines = self.event_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), len(records))
        parsed = [json.loads(line) for line in lines]
        for original, line_obj in zip(records, parsed):
            self.assertEqual(line_obj, original)


if __name__ == "__main__":  # pragma: no cover - direct execution support
    unittest.main()
