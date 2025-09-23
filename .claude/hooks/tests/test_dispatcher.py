from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Dict, Optional

import pytest
from common_test_utils import run_hook
import json


HOOKS_DIR = Path(__file__).resolve().parents[1]
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

herald_module = importlib.import_module("herald")

DispatchContext = herald_module.DispatchContext
HandlerResult = herald_module.HandlerResult
HeraldDispatcher = herald_module.HeraldDispatcher
build_default_dispatcher = herald_module.build_default_dispatcher


class FakeAudioManager:
    def __init__(self):
        self.play_calls: list[tuple[str, bool]] = []
        self.marked: list[str] = []
        self.throttle_window_overrides: Dict[str, int] = {}
        self.should_throttle_next: bool = False
        self.return_path = Path("/tmp/test.wav")

    def get_throttle_window(self, audio_type: str, default_seconds: int) -> int:
        return self.throttle_window_overrides.get(audio_type, default_seconds)

    def should_throttle(self, key: str, window_seconds: int) -> bool:
        self.last_throttle_args = (key, window_seconds)
        return self.should_throttle_next

    def play_audio(self, audio_type: str, enabled: bool = False) -> tuple[bool, Optional[Path]]:
        self.play_calls.append((audio_type, enabled))
        return (True, self.return_path)

    def mark_emitted(self, key: str) -> None:
        self.marked.append(key)

    def resolve_file(self, audio_type: str) -> Optional[Path]:
        return self.return_path


def make_dispatcher(fake_audio: FakeAudioManager) -> HeraldDispatcher:
    dispatcher = HeraldDispatcher(audio_manager=fake_audio)

    def _handler(context: DispatchContext) -> HandlerResult:
        return HandlerResult(audio_type="Notification", throttle_window=15, notes=["handled"])

    dispatcher.register_handler("Notification", _handler)
    return dispatcher


def test_dispatch_play_audio_when_not_throttled():
    fake_audio = FakeAudioManager()
    dispatcher = make_dispatcher(fake_audio)

    report = dispatcher.dispatch("Notification", payload={"message": "Ping"}, enable_audio=True)

    assert report.handled is True
    assert report.audio_played is True
    assert report.audio_type == "Notification"
    assert report.audio_path == fake_audio.return_path
    assert fake_audio.play_calls == [("Notification", True)]
    assert fake_audio.marked, "mark_emitted should be invoked when audio fires"
    assert report.response["continue"] is True
    assert "handled" in report.notes


def test_dispatch_skips_audio_when_throttled():
    fake_audio = FakeAudioManager()
    fake_audio.should_throttle_next = True
    dispatcher = make_dispatcher(fake_audio)

    report = dispatcher.dispatch("Notification", payload={"message": "Ping"}, enable_audio=True)

    assert report.throttled is True
    assert report.audio_played is False
    assert fake_audio.play_calls == []
    assert not fake_audio.marked


def test_default_dispatcher_uses_hooks():
    fake_audio = FakeAudioManager()
    dispatcher = build_default_dispatcher(audio_manager=fake_audio)

    report = dispatcher.dispatch("Notification", payload={"message": "Ping"}, enable_audio=True)

    assert fake_audio.play_calls == [("Notification", True)]
    assert report.response["continue"] is True
    assert report.errors == []


def test_default_dispatcher_precompact_noop():
    fake_audio = FakeAudioManager()
    dispatcher = build_default_dispatcher(audio_manager=fake_audio)

    report = dispatcher.dispatch("PreCompact", payload={"context": "noop"}, enable_audio=True)

    assert report.handled is True
    assert report.audio_played is False
    assert report.throttled is False
    assert report.response["continue"] is True
    assert fake_audio.play_calls == []


def test_middleware_can_stop_dispatch():
    fake_audio = FakeAudioManager()
    dispatcher = HeraldDispatcher(audio_manager=fake_audio)

    def stop_middleware(context: DispatchContext) -> None:
        context.stop_dispatch = True

    dispatcher.register_middleware(stop_middleware)

    def handler(_: DispatchContext) -> HandlerResult:
        pytest.fail("handler should not run when dispatch is stopped")

    dispatcher.register_handler("Notification", handler)

    report = dispatcher.dispatch("Notification", payload={})

    assert report.handled is False
    assert report.audio_played is False
    assert report.throttled is False
    assert report.handler_name == handler.__name__


def test_herald_cli_interface_basic():
    """Tests the basic CLI execution of herald.py."""
    result = run_hook(
        ".claude/hooks/herald.py",
        payload={"message": "CLI test"},
        args=["--hook", "Notification", "--enable-audio"]
    )
    assert result.returncode == 0
    # stderr should contain the debug report
    assert "[Herald] event=Notification" in result.stderr
    assert "handler=" in result.stderr
    assert "handled=True" in result.stderr
    # stdout should contain the JSON response
    assert '"continue": true' in result.stdout
    # Ensure it's valid JSON
    assert json.loads(result.stdout) == {"continue": True}


def test_herald_cli_interface_invalid_hook():
    """Tests the CLI with an invalid or unhandled hook name."""
    result = run_hook(
        ".claude/hooks/herald.py",
        payload={},
        args=["--hook", "InvalidHookName"]
    )
    assert result.returncode == 0
    assert "[Herald] event=InvalidHookName" in result.stderr
    assert "[Herald] handler=none" in result.stderr
    assert "[Herald] handled=False" in result.stderr
    # The default response should still be a valid continue
    assert json.loads(result.stdout) == {"continue": True}
