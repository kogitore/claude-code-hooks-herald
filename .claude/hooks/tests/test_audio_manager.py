"""Tests for the simplified audio manager implementation."""
from __future__ import annotations

from pathlib import Path

import pytest

from utils import audio_manager


def test_resolve_file_uses_injected_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """AudioManager should resolve mapped audio types using the loaded config."""

    sound_file = tmp_path / "notification.wav"
    sound_file.write_bytes(b"RIFF")

    def fake_load_config(_repo_root: Path) -> tuple[audio_manager.AudioConfig, float, dict[str, int]]:
        config = audio_manager.AudioConfig(base_path=tmp_path, mappings={"Notification": sound_file.name})
        return config, 0.5, {"Notification": 10}

    monkeypatch.setattr(audio_manager, "_load_config", fake_load_config)
    monkeypatch.setattr(audio_manager.AudioManager, "_select_player", lambda self: (None, []))

    manager = audio_manager.AudioManager()

    assert manager.resolve_file("Notification") == sound_file
    assert manager.resolve_file("Stop") is None


def test_play_audio_without_player_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no player command is available the manager should skip playback."""

    monkeypatch.setattr(audio_manager.AudioManager, "_select_player", lambda self: (None, []))
    manager = audio_manager.AudioManager()

    played, path, context = manager.play_audio_safe("Notification")

    assert played is False
    assert path is None
    assert context["status"] == "skipped"
    assert context["reason"] == "no_player"


def test_throttle_tracking_blocks_replays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Throttle helpers must prevent rapid repeat notifications for the same key."""

    monkeypatch.setattr(audio_manager.AudioManager, "_select_player", lambda self: (None, []))
    manager = audio_manager.AudioManager()

    assert manager.should_throttle_safe("notification", 10) is False
    manager.mark_emitted_safe("notification")
    assert manager.should_throttle_safe("notification", 10) is True
