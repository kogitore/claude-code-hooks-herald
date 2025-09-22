<div align="center">

[English](./README.md) | [繁體中文](./README_zh-TW.md)

**Changelog:** see [CHANGELOG.md](./CHANGELOG.md) · **Design/Notes:** see [/updates](./updates/)

</div>

> Inspired by [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

# Claude Code Hooks Herald

Unified dispatcher + audio-only hook system for Claude Code. Herald routes every official event through a single entry point, plays local audio with throttling, and applies a configurable safety policy before tools run.

## Features

- 🛡️ **Herald dispatcher** – Single entry point (`.claude/hooks/herald.py`) for Notification / Stop / SubagentStop / PreToolUse / PostToolUse / Session events.
- 🧩 **BaseHook framework** – Shared validation + playback pipeline keeps individual hooks tiny and reliable.
- 🧠 **Decision API** – Allow/Deny/Ask/BlockStop responses with user overrides via `decision_policy.json`.
- 🔔 **Audio feedback** – Local `.wav` playback for notifications and completion cues.
- ⏱️ **Smart throttling** – Config-driven per-event cooldowns to prevent sound spam.

## Quick Start

This project requires no complex installation. The minimal steps to get started are:

1. **Provide sound files:** Place `.wav` files in `.claude/sounds/`.
2. **Confirm settings:** `.claude/settings.json` is already wired to run `herald.py` for every event. Copy it into your Claude project if necessary.
3. **Run hooks:** Claude Code will invoke Herald automatically; you can also test manually (see CLI section).

## Configuration

### Audio mappings

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

### Decision policy

Safety decisions (Allow / Deny / Ask / BlockStop) are defined in `.claude/hooks/utils/decision_policy.json`. Add custom rules under `pre_tool_use.rules` or tweak `post_tool_use` / `stop` behaviour. Example rule:

```json
{
  "pre_tool_use": {
    "rules": [
      {
        "type": "command",
        "action": "deny",
        "pattern": "git\\s+reset\\s+--hard",
        "reason": "Confirm before wiping all changes"
      }
    ]
  }
}
```

User rules are appended to the defaults, so built-in protections remain active.

**Quick start:** copy `.claude/hooks/utils/decision_policy.example.json` to `decision_policy.json`, remove the sections you do not need, then adjust regex patterns/reasons. The template documents common scenarios (package installs, git resets, credential files) and defaults to `allow` when no rule matches. See [updates/decisions/0003-decision-policy-template.md](./updates/decisions/0003-decision-policy-template.md) for full guidance.

**Built-in tags** (usable in the `tags` array):

- `system:dangerous` → matches destructive commands like `rm -rf /`, `shutdown`, `reboot` (severity `critical`).
- `package:install` → package manager installs/updates (`npm install`, `pip install`, `uv pip`, …) (severity `medium`).
- `git:destructive` → state-resetting git commands (`git reset --hard`, `git clean -fd`, …) (severity `high`).
- `secrets:file` → credential/secret file paths (`.env`, `id_rsa`, `*.pem`) (severity `high`).
- `dependency:lock` → dependency lock files (`package-lock.json`, `poetry.lock`, `requirements.txt`) (severity `medium`).

Add your own regex alongside tags for project-specific needs; unknown tags are ignored with no errors.

## Audio Files

Provide your own `.wav` files in `.claude/sounds/`:

- `task_complete.wav` – Played for Stop events
- `agent_complete.wav` – Played for SubagentStop events
- `user_prompt.wav` – Played for Notifications

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
- Integration tests verify `.claude/settings.json` routes all events through Herald and that decision policies trigger correctly.

## License

MIT License - see LICENSE file for details

## Acknowledgments

This project was inspired by Claude Code's hook system examples and the [claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) project.

## Output & Environment

- JSON-only output: each hook prints a single JSON object (e.g. `{"continue": true}` or decision payloads).
- Environment overrides: set audio folder via environment (takes precedence over config)
  - `CLAUDE_SOUNDS_DIR` or `AUDIO_SOUNDS_DIR`
  - Example:

```
export CLAUDE_SOUNDS_DIR="/absolute/path/to/sounds"
```

## CLI Examples

- Herald dispatcher (Notification):

```
echo '{"message": "Hi"}' | uv run .claude/hooks/herald.py --hook Notification --enable-audio
```

- PreToolUse policy check:

```
echo '{"tool": "bash", "toolInput": {"command": "rm -rf /"}}' | uv run .claude/hooks/herald.py --hook PreToolUse
```
