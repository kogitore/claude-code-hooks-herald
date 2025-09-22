from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


HOOKS_DIR = Path(__file__).resolve().parents[1]
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

base_module = importlib.import_module("utils.base_hook")

BaseHook = base_module.BaseHook
HookExecutionResult = base_module.HookExecutionResult


class FakeAudioManager:
    def __init__(self) -> None:
        self.resolve_calls: list[str] = []
        self.play_calls: list[tuple[str, bool]] = []
        self.mark_calls: list[str] = []
        self.should_throttle_keys: dict[str, bool] = {}
        self.window_overrides: dict[str, int] = {}
        self.return_path = Path("/tmp/fake.wav")

    def resolve_file(self, audio_type: str) -> Path:
        self.resolve_calls.append(audio_type)
        return self.return_path

    def should_throttle(self, key: str, window_seconds: int) -> bool:
        self.last_throttle = (key, window_seconds)
        return self.should_throttle_keys.get(key, False)

    def play_audio(self, audio_type: str, enabled: bool = False):
        self.play_calls.append((audio_type, enabled))
        return True, self.return_path

    def mark_emitted(self, key: str) -> None:
        self.mark_calls.append(key)

    def get_throttle_window(self, audio_type: str, default_seconds: int) -> int:
        return self.window_overrides.get(audio_type, default_seconds)


class SampleHook(BaseHook):
    default_audio_event = "Notification"
    default_throttle_seconds = 25

    def __init__(self, audio_manager: FakeAudioManager):
        super().__init__(audio_manager=audio_manager)

    def validate_input(self, data):
        return isinstance(data, dict) and "message" in data

    def process(self, data):
        return {"message": data["message"], "marker": data.get("marker", "abc"), "extra": 1}

    def handle_error(self, error: Exception):
        return {"error": str(error)}


def test_execute_success_with_audio():
    fake_audio = FakeAudioManager()
    hook = SampleHook(fake_audio)

    payload = {"message": "Hello", "marker": "m01"}
    result: HookExecutionResult = hook.execute(payload, enable_audio=True)

    assert result.payload["extra"] == 1
    response = result.build_response()
    assert response["continue"] is True
    assert result.audio_played is True
    assert result.audio_path == fake_audio.return_path
    assert result.throttled is False
    assert fake_audio.play_calls == [("Notification", True)]
    assert fake_audio.mark_calls == ["Notification:m01"]
    assert result.throttle_window == fake_audio.get_throttle_window("Notification", hook.default_throttle_seconds)


def test_execute_invalid_input_suppresses_audio():
    fake_audio = FakeAudioManager()
    hook = SampleHook(fake_audio)

    result = hook.execute({}, enable_audio=True)

    assert "input_validation_failed" in result.errors
    assert fake_audio.play_calls == []
    assert fake_audio.mark_calls == []


def test_execute_error_path_uses_handle_error():
    fake_audio = FakeAudioManager()

    class ErrorHook(SampleHook):
        def process(self, data):
            raise RuntimeError("boom")

    hook = ErrorHook(fake_audio)
    result = hook.execute({"message": "Hi"}, enable_audio=True)

    assert "RuntimeError" in result.errors
    assert result.payload.get("error") == "boom"
    assert fake_audio.play_calls == []
    assert result.audio_played is False


def test_execute_throttled_skips_playback_and_marks_note():
    fake_audio = FakeAudioManager()
    hook = SampleHook(fake_audio)

    # Compute expected throttle key based on message content digest fallback
    payload = {"message": "Repeat me"}
    result = hook.execute(payload, enable_audio=True)
    assert fake_audio.mark_calls, "initial execution should mark throttle key"
    throttle_key = fake_audio.mark_calls[0]

    fake_audio.should_throttle_keys[throttle_key] = True
    fake_audio.play_calls.clear()
    fake_audio.mark_calls.clear()

    throttled_result = hook.execute(payload, enable_audio=True)

    assert fake_audio.play_calls == []
    assert fake_audio.mark_calls == []
    assert throttled_result.notes
    assert "Throttled" in throttled_result.notes[0]
