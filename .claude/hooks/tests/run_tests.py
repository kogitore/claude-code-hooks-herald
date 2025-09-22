#!/usr/bin/env python3
"""
Lightweight runner for audio hooks tests (folder renamed to 'tests').

This runner invokes the existing test scripts under 'test/' to avoid churn.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    p = Path(__file__).resolve()
    for anc in p.parents:
        if (anc / ".claude").exists():
            return anc
    return p.parents[3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-sound", action="store_true", help="Demo local audio playback after each test")
    ap.add_argument("--sounds", type=str, default=None, help="Path to sounds dir (defaults to autodetect)")
    args = ap.parse_args()

    tests = [
        # 現有測試
        ".claude/hooks/tests/test_notification.py",
        ".claude/hooks/tests/test_stop.py",
        ".claude/hooks/tests/test_subagent_stop.py",
        ".claude/hooks/tests/test_throttle.py",
        ".claude/hooks/tests/test_json_only.py",
        ".claude/hooks/tests/test_audio_played_and_timeout.py",
        # 新增模組測試
        ".claude/hooks/tests/test_session_storage.py",
        ".claude/hooks/tests/test_user_prompt_submit.py",
        ".claude/hooks/tests/test_pre_tool_use.py",
        ".claude/hooks/tests/test_post_tool_use.py",
        ".claude/hooks/tests/test_session_management.py",
    ]

    rc_accum = 0
    for t in tests:
        cmd = [sys.executable, str(repo_root() / t)]
        if args.demo_sound:
            cmd.append("--demo-sound")
        if args.sounds:
            cmd.extend(["--sounds", args.sounds])
        print(f"\n>>> Running {t}")
        rc = subprocess.call(cmd)
        rc_accum |= (rc & 0xFF)

    print(f"\nAll tests done. aggregate_rc={rc_accum}")
    return rc_accum


if __name__ == "__main__":
    raise SystemExit(main())
