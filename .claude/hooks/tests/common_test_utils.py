#!/usr/bin/env python3
"""Common test utilities for hooks testing."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict


def repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[3]


class RunResult:
    """Result of running a hook script."""
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_hook(script_relpath: str, payload: Dict[str, Any] | None = None, args: list[str] | None = None) -> RunResult:
    """Run a hook script with given payload and arguments."""
    repo = repo_root()
    script_path = repo / script_relpath

    cmd = ["python3", str(script_path)]
    if args:
        cmd.extend(args)

    payload_json = json.dumps(payload or {})

    try:
        result = subprocess.run(
            cmd,
            input=payload_json,
            text=True,
            capture_output=True,
            cwd=repo,
            env={"AUDIO_PLAYER_CMD": "true"}  # Disable audio during tests
        )
        return RunResult(result.returncode, result.stdout, result.stderr)
    except Exception as e:
        return RunResult(1, "", str(e))