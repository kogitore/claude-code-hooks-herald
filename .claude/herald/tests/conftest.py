"""Shared pytest fixtures for hook tests."""
from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest


# =============================================================================
# Dispatcher Helper for Unit Tests
# =============================================================================

class DispatchReport:
    """Wrapper for dispatch response to match test expectations."""

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response


class DefaultDispatcher:
    """Test dispatcher that wraps herald.dispatch for unit tests."""

    def dispatch(self, event: str, payload: dict[str, object] | None = None) -> DispatchReport:
        """Dispatch an event and return wrapped response."""
        from herald.dispatcher import dispatch
        response = dispatch(event, payload or {})
        return DispatchReport(response)


def build_default_dispatcher() -> DefaultDispatcher:
    """Factory function for creating test dispatchers.

    This is injected into test modules via conftest to provide
    a consistent dispatcher interface for unit tests.
    """
    return DefaultDispatcher()


# Inject into builtins so tests can use it without explicit import
import builtins
builtins.build_default_dispatcher = build_default_dispatcher  # type: ignore[attr-defined]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the repository root detected from this test directory."""
    return Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def claude_dir(repo_root: Path) -> Path:
    """Path to the .claude directory for imports."""
    return repo_root / ".claude"


@pytest.fixture(autouse=True)
def _pythonpath(claude_dir: Path) -> Generator[None, None, None]:
    """Inject .claude dir into sys.path for herald module imports."""
    sys.path.insert(0, str(claude_dir))
    try:
        yield
    finally:
        if sys.path and sys.path[0] == str(claude_dir):
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
    from herald import dispatcher  # type: ignore[import-not-found]

    # Use a fresh list per test run to avoid class-level mutable default issues
    shared_played_calls: list[tuple[str, bool, dict[str, object]]] = []

    class _StubAudioManager:
        """Minimal AudioManager stub that records invocations.

        Note: played_calls is now passed in from the enclosing scope to avoid
        class-level mutable default which can cause test pollution.
        """

        def __init__(self) -> None:
            self._plays: list[tuple[str, bool, dict[str, object]]] = []

        def should_throttle_safe(self, key: str, window_seconds: int) -> bool:  # noqa: D401
            return False

        def mark_emitted_safe(self, key: str) -> None:  # noqa: D401
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
            shared_played_calls.append(record)
            return False, None, ctx

        @classmethod
        def get_played_calls(cls) -> list[tuple[str, bool, dict[str, object]]]:
            """Access shared played calls from enclosing scope."""
            return shared_played_calls

    monkeypatch.setattr(dispatcher, "_AM", _StubAudioManager)
    yield SimpleNamespace(audio_stub=_StubAudioManager, played_calls=shared_played_calls)
    shared_played_calls.clear()
