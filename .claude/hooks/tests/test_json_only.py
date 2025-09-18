#!/usr/bin/env python3
from __future__ import annotations

import json
from common_test_utils import run_hook


def test_json_only_output() -> None:
    r = run_hook(
        script_relpath=".claude/hooks/notification.py",
        payload={"hookEventName": "Notification", "message": "json only"},
        args=["--enable-audio", "--json-only"],
    )
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
    # In json-only mode, only JSON line should be present
    assert len(lines) == 1
    obj = json.loads(lines[-1])
    assert obj["continue"] is True
