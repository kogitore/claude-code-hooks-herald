#!/usr/bin/env python3
"""Convenience runner for executing the pytest-based hook suite."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    """Locate the repository root by climbing parent directories."""
    current = Path(__file__).resolve()
    for ancestor in current.parents:
        if (ancestor / ".claude").exists():
            return ancestor
    return current.parents[3]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Claude hook tests via pytest")
    parser.add_argument("pytest_args", nargs="*", help="Arguments forwarded to pytest")
    args = parser.parse_args()

    root = repo_root()
    tests_dir = root / ".claude" / "hooks" / "tests"
    env = os.environ.copy()
    hooks_root = root / ".claude" / "hooks"
    env["PYTHONPATH"] = str(hooks_root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    command = [sys.executable, "-m", "pytest", str(tests_dir), *args.pytest_args]
    result = subprocess.run(command, cwd=root, env=env, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
