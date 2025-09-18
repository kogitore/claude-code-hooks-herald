#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from common_test_utils import run_hook


def test_subagent_stop_basic() -> None:
    payload = {"hookEventName": "SubagentStop", "status": "SubagentComplete"}
    marker = hashlib.sha1(str(payload).encode()).hexdigest()[:8]
    payload["marker"] = marker
    r = run_hook(
        script_relpath=".claude/hooks/subagent_stop.py",
        payload=payload,
        args=["--enable-audio"],
    )
    assert r.returncode == 0
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
    obj = json.loads(lines[-1])
    assert obj["continue"] is True
    assert "[SubagentStop]" in r.stderr
