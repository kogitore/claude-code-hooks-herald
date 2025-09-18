<div align="center">

[English](./README.md) | [繁體中文](./README_zh-TW.md)

</div>

> Inspired by [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

# Claude Code Hooks Herald

A collection of audio enhancement hooks for Claude Code that provides sound feedback for various development events.

## Features

- 🔔 **Notification sounds** - Audio feedback for user prompts
- ✅ **Task completion sounds** - Audio confirmation when tasks finish
- 🎯 **Subagent completion sounds** - Special audio for subagent tasks
- ⏱️ **Smart throttling** - Prevents audio spam with intelligent caching
- 🎵 **Local audio files** - Uses your own .wav files, no API keys required

## Quick Start

This project requires no complex installation. The minimal steps to get started are:

1.  **Provide Sound Files:** Place your `.wav` audio files inside the `.claude/sounds/` directory.
2.  **Name Them Correctly:** Ensure the filenames match those expected by the configuration (e.g., `user_prompt.wav`, `task_complete.wav`).

That's it! The hooks will automatically pick up the sounds. For more advanced changes, see the configuration details below.

## Configuration

Audio settings are managed through `.claude/hooks/utils/audio_config.json`:

```json
{
  "audio_settings": {
    "enabled": true,
    "mode": "audio_files",
    "volume": 0.2
  },
  "sound_files": {
    "base_path": "./.claude/sounds",
    "mappings": {
      "stop": "task_complete.wav",
      "agent_stop": "agent_complete.wav",
      "subagent_stop": "agent_complete.wav",
      "user_notification": "user_prompt.wav"
    }
  }
}
```

## Audio Files

You'll need to provide your own .wav audio files in the `.claude/sounds/` directory:
- `task_complete.wav` - Played when tasks complete
- `agent_complete.wav` - Played when subagents finish
- `user_prompt.wav` - Played for user notifications

## Testing

Run the pytest suite from the repo root (no venv needed):

```
# Option A: use uv to run pytest without installing it globally
uvx pytest -q .claude/hooks/tests

# Option B: pip install locally
pip install -U pytest && pytest -q .claude/hooks/tests
```

Notes:
- Tests default to a no-op player via `AUDIO_PLAYER_CMD=true` so they don't require system audio.
- To exercise real playback locally, unset that env and ensure `.claude/sounds/` contains the wav files.

## License

MIT License - see LICENSE file for details

## Acknowledgments

This project was inspired by Claude Code's hook system examples and the [claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) project.

## Output & Environment

- JSON-only output: each hook prints a single JSON object with `hookSpecificOutput`.

```
{"hookSpecificOutput": {"hookEventName": "UserNotification", "status": "completed", "audioPlayed": true, "throttled": false, "notes": []}}
```

- Environment overrides: set audio folder via environment (takes precedence over config)
  - `CLAUDE_SOUNDS_DIR` or `AUDIO_SOUNDS_DIR`
  - Example:

```
export CLAUDE_SOUNDS_DIR="/absolute/path/to/sounds"
```

## CLI Examples

- Notification (play sound):

```
echo '{}' | uv run .claude/hooks/notification.py --enable-audio
```

- Task complete (play sound):

```
echo '{}' | uv run .claude/hooks/stop.py --enable-audio
```

- Subagent complete (play sound):

```
echo '{}' | uv run .claude/hooks/subagent_stop.py --enable-audio
```
