"""Utility helpers for exercising hook entrypoints in tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RunResult:
    """Captured result of invoking a hook script via subprocess."""

    returncode: int
    stdout: str
    stderr: str

    def json(self) -> dict[str, Any]:
        """Parse the last non-empty stdout line as JSON."""
        lines = [line for line in self.stdout.splitlines() if line.strip()]
        if not lines:
            raise ValueError("Hook produced no JSON output")
        return json.loads(lines[-1])


def repo_root() -> Path:
    """Return the repository root detected from this file location."""
    return Path(__file__).resolve().parents[3]


def run_hook(
    script_relpath: str,
    payload: Mapping[str, Any] | None = None,
    args: Sequence[str] | None = None,
    *,
    timeout: float = 5.0,
    env: Mapping[str, str] | None = None,
) -> RunResult:
    """Execute a hook script with a JSON payload and capture its output."""
    root = repo_root()
    script_path = root / script_relpath
    command = [sys.executable, str(script_path)]
    if args:
        command.extend(args)

    base_env = os.environ.copy()
    base_env.setdefault("AUDIO_PLAYER_CMD", "true")
    base_env.setdefault("AUDIO_PLAYER_ARGS", "")
    if env:
        base_env.update(env)

    payload_json = json.dumps(dict(payload or {}), ensure_ascii=False)

    completed = subprocess.run(
        command,
        input=payload_json,
        text=True,
        capture_output=True,
        cwd=root,
        env=base_env,
        timeout=timeout,
    )
    return RunResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
