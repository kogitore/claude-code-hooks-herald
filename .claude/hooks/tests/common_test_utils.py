#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional, List, Dict
from pathlib import Path


@dataclass
class HookResult:
    returncode: int
    stdout: str
    stderr: str
    duration_sec: float


def repo_root() -> Path:
    """Locate repository root by looking for a directory that contains '.claude'.

    Works both when this code lives at <root>/.claude/hooks/test and when the
    repository is nested under another workspace.
    """
    p = Path(__file__).resolve()
    for anc in p.parents:
        if (anc / ".claude").exists():
            return anc
    # Fallback to <parent of .claude/hooks/test>.
    return p.parents[3]


def run_hook(script_relpath: str, payload: Optional[dict] = None, args: Optional[List[str]] = None, timeout: float = 5.0, env_overrides: Optional[Dict[str, str]] = None) -> HookResult:
    """Run a hook script as a subprocess, feeding JSON on stdin.

    - script_relpath: path relative to repo root (e.g., '.claude/hooks/notification.py')
    - payload: dict to be json-dumped to stdin; if None, an empty object is sent
    - args: extra CLI args for the hook
    - timeout: seconds before killing the process
    """
    # Resolve script path robustly by scanning ancestors
    candidates: List[Path] = []
    for anc in Path(__file__).resolve().parents:
        candidates.append(anc / script_relpath)
    # Also try joining with discovered repo_root()
    candidates.insert(0, repo_root() / script_relpath)
    script_path: Optional[Path] = None
    for c in candidates:
        if c.exists():
            script_path = c
            break
    if script_path is None:
        raise FileNotFoundError(f"Hook script not found via search: {script_relpath}")

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    stdin_bytes = (json.dumps(payload or {}) + "\n").encode("utf-8")

    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    # Provide a stable cwd for hooks to resolve relative paths
    cwd = str(script_path.parent)

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=stdin_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
        duration = time.time() - start
        return HookResult(
            returncode=proc.returncode,
            stdout=proc.stdout.decode("utf-8", errors="replace"),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
            duration_sec=duration,
        )
    except subprocess.TimeoutExpired as e:
        duration = time.time() - start
        return HookResult(
            returncode=124,
            stdout=(e.stdout or b"").decode("utf-8", errors="replace"),
            stderr=f"Timeout after {timeout}s: {(e.stderr or b'').decode('utf-8', errors='replace')}",
            duration_sec=duration,
        )


def find_sounds_dir(preferred: Optional[str] = None) -> Optional[Path]:
    """Find the sounds directory, trying several candidates.

    Priority:
    1) preferred (if provided)
    2) <repo>/sounds
    3) (legacy paths removed)
    """
    if preferred:
        p = Path(preferred)
        if p.exists():
            return p
    root = repo_root()
    cands = [
        root / ".claude" / "sounds",
        root / "sounds",  # legacy
    ]
    for c in cands:
        if c.exists():
            return c
    return None


def afplay(path: Path) -> tuple[int, str, str]:
    """Play a wav file using macOS 'afplay' if available.

    Returns (rc, out, err). If 'afplay' not found, returns (127, '', 'afplay not found').
    """
    from shutil import which

    if which("afplay") is None:
        return 127, "", "afplay not found"
    p = subprocess.run(["afplay", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def print_result(title: str, result: HookResult, success_markers: Optional[List[str]] = None) -> None:
    print(f"=== {title} ===")
    print(f"rc={result.returncode} time={result.duration_sec:.3f}s")
    if result.stdout.strip():
        print("-- stdout --\n" + result.stdout.strip())
    if result.stderr.strip():
        print("-- stderr --\n" + result.stderr.strip())
    ok = result.returncode == 0
    if success_markers:
        ok = ok and any(m in result.stdout for m in success_markers)
    print("RESULT:", "PASS" if ok else "PENDING" if result.returncode == 0 else "FAIL")
