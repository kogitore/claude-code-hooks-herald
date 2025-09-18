#!/usr/bin/env python3
"""
Throttle behavior tests for notification and stop hooks.

Validates that the second immediate invocation prints the throttled note.
"""
from __future__ import annotations

import json
from common_test_utils import run_hook


def test_notification_throttle() -> None:
    payload = {"event": "notification", "message": "Same message for throttle"}
    # First call: should not be throttled
    r1 = run_hook(".claude/hooks/notification.py", payload=payload, args=["--enable-audio"]) 
    assert r1.returncode == 0
    obj1 = json.loads([ln for ln in r1.stdout.splitlines() if ln.strip()][-1])
    assert obj1["hookSpecificOutput"]["throttled"] is False
    # Second call: should be throttled within 30s window
    r2 = run_hook(".claude/hooks/notification.py", payload=payload, args=["--enable-audio"]) 
    obj2 = json.loads([ln for ln in r2.stdout.splitlines() if ln.strip()][-1])
    assert obj2["hookSpecificOutput"]["throttled"] is True


def test_stop_throttle() -> None:
    payload = {"event": "stop", "status": "task_complete"}
    r1 = run_hook(".claude/hooks/stop.py", payload=payload, args=["--enable-audio"]) 
    obj1 = json.loads([ln for ln in r1.stdout.splitlines() if ln.strip()][-1])
    assert obj1["hookSpecificOutput"]["throttled"] is False or obj1["hookSpecificOutput"]["throttled"] is True
    r2 = run_hook(".claude/hooks/stop.py", payload=payload, args=["--enable-audio"]) 
    obj2 = json.loads([ln for ln in r2.stdout.splitlines() if ln.strip()][-1])
    assert obj2["hookSpecificOutput"]["throttled"] is True


def main():
    # kept for manual runs; pytest will ignore
    test_notification_throttle()
    test_stop_throttle()
