#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import pytest


def _repo_root(start: Path) -> Path:
    for anc in [start] + list(start.parents):
        if (anc / ".claude").exists():
            return anc
    return start


@pytest.fixture(autouse=True)
def clean_throttle(tmp_path_factory):
    """Remove throttle file before each test to avoid cross-test interference."""
    root = _repo_root(Path(__file__).resolve())
    throttle = root / "logs" / "audio_throttle.json"
    try:
        throttle.unlink()
    except FileNotFoundError:
        pass
    yield


@pytest.fixture(autouse=True)
def env_default_player(monkeypatch: pytest.MonkeyPatch):
    """Default to a no-op player so tests don't depend on system audio."""
    monkeypatch.setenv("AUDIO_PLAYER_CMD", "true")
    # keep default timeout small for tests
    monkeypatch.setenv("AUDIO_PLAYER_TIMEOUT", "2")
    yield

