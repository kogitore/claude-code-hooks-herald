#!/usr/bin/env python3
"""
Lightweight runner for audio hooks tests (folder renamed to 'tests').

This runner invokes the existing test scripts under 'test/' to avoid churn.
"""
from __future__ import annotations

import argparse
import os
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

    # Curated 8-file suite (Phase 2/3 slimming)
    tests = [
        # Hook functionality
        ".claude/hooks/tests/test_notification.py",
        ".claude/hooks/tests/test_stop.py",

        # Security/decision flows
        ".claude/hooks/tests/test_pre_tool_use.py",
        ".claude/hooks/tests/test_post_tool_use.py",

        # Prompt and session lifecycle
        ".claude/hooks/tests/test_user_prompt_submit.py",
        ".claude/hooks/tests/test_session_management.py",

        # Config + integration sanity
        ".claude/hooks/tests/test_config_manager.py",
        ".claude/hooks/tests/test_herald_integration.py",
    ]

    rc_accum = 0
    hooks_root = repo_root() / ".claude" / "hooks"
    base_env = os.environ.copy()
    # Prepend hooks_root to PYTHONPATH so 'utils' package resolves in tests
    base_env["PYTHONPATH"] = str(hooks_root) + (os.pathsep + base_env["PYTHONPATH"] if base_env.get("PYTHONPATH") else "")

    for t in tests:
        cmd = [sys.executable, str(repo_root() / t)]
        if args.demo_sound:
            cmd.append("--demo-sound")
        if args.sounds:
            cmd.extend(["--sounds", args.sounds])
        print(f"\n>>> Running {t}")
        # Skip pytest-dependent tests if pytest is not available
        if t.endswith("test_dispatcher.py"):
            try:
                import pytest  # noqa: F401
            except Exception:
                print(f"Skipping {t} (pytest not installed)")
                continue
        # If test file was removed or moved, skip gracefully
        test_path = repo_root() / t
        if not test_path.exists():
            print(f"Skipping {t} (file not found)")
            continue
        rc = subprocess.call(cmd, env=base_env)
        rc_accum |= (rc & 0xFF)

    print(f"\nAll tests done. aggregate_rc={rc_accum}")
    return rc_accum


if __name__ == "__main__":
    raise SystemExit(main())
