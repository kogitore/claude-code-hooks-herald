#!/usr/bin/env python3
"""Common test utilities for hooks testing."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[3]


class RunResult:
    """Result of running a hook script."""
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_hook(script_relpath: str, payload: dict[str, object] | None = None, args: list[str] | None = None) -> RunResult:
    """Run a hook script with given payload and arguments."""
    import os
    repo = repo_root()
    script_path = repo / script_relpath

    cmd = ["python3", str(script_path)]
    if args:
        cmd.extend(args)

    payload_json = json.dumps(payload or {})

    # Prepare environment with PYTHONPATH for herald imports
    env = os.environ.copy()
    claude_dir = str(repo / ".claude")
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = claude_dir + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = claude_dir
    env["AUDIO_PLAYER_CMD"] = "true"  # Disable audio during tests

    try:
        result = subprocess.run(
            cmd,
            input=payload_json,
            text=True,
            capture_output=True,
            cwd=repo,
            env=env,
        )
        return RunResult(result.returncode, result.stdout, result.stderr)
    except Exception as e:
        return RunResult(1, "", str(e))