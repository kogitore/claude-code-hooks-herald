"""Shared pytest fixtures for hook tests."""
from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the repository root detected from this test directory."""
    return Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def hooks_root(repo_root: Path) -> Path:
    """Path to the hooks package inserted on PYTHONPATH for imports."""
    return repo_root / ".claude" / "hooks"


@pytest.fixture(autouse=True)
def _pythonpath(hooks_root: Path) -> Generator[None, None, None]:
    """Inject hooks_root into sys.path for direct module imports."""
    sys.path.insert(0, str(hooks_root))
    try:
        yield
    finally:
        if sys.path and sys.path[0] == str(hooks_root):
            sys.path.pop(0)


@pytest.fixture(autouse=True)
def _stable_audio_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure audio playback is stubbed to a no-op command for all tests."""
    monkeypatch.setenv("AUDIO_PLAYER_CMD", "true")
    monkeypatch.setenv("AUDIO_PLAYER_ARGS", "")
    monkeypatch.setenv("AUDIO_PLAYER_TIMEOUT", "1")


@pytest.fixture(autouse=True)
def _clean_throttle(repo_root: Path) -> Generator[None, None, None]:
    """Remove persisted throttle metadata before every test run."""
    throttle_file = repo_root / "logs" / "audio_throttle.json"
    if throttle_file.exists():
        throttle_file.unlink()
    yield
    if throttle_file.exists():
        throttle_file.unlink()


@pytest.fixture(autouse=True)
def _herald_state(monkeypatch: pytest.MonkeyPatch):
    """Reset herald caches and silence audio feedback for deterministic tests."""
    import herald  # type: ignore[import-not-found]

    herald._handlers_cache = None  # noqa: SLF001 - test scaffolding

    class _StubAudioManager:
        """Minimal AudioManager stub that records invocations."""

        played_calls: list[tuple[str, bool, dict[str, object]]] = []

        def __init__(self) -> None:
            self._plays: list[tuple[str, bool, dict[str, object]]] = []

        def should_throttle_safe(self, key: str, window_seconds: int) -> bool:  # noqa: D401 - simple delegator
            return False

        def mark_emitted_safe(self, key: str) -> None:  # noqa: D401 - simple delegator
            return None

        def play_audio_safe(
            self,
            audio_type: str,
            enabled: bool = True,
            additional_context: dict[str, object] | None = None,
        ) -> tuple[bool, None, dict[str, object]]:
            ctx = {
                "audioType": audio_type,
                "enabled": enabled,
                **(additional_context or {}),
                "status": "skipped",
                "reason": "stubbed",
            }
            record = (audio_type, enabled, additional_context or {})
            self._plays.append(record)
            _StubAudioManager.played_calls.append(record)
            return False, None, ctx

    _StubAudioManager.played_calls.clear()
    monkeypatch.setattr(herald, "_AM", _StubAudioManager)
    yield SimpleNamespace(audio_stub=_StubAudioManager)
    _StubAudioManager.played_calls.clear()
    herald._handlers_cache = None
