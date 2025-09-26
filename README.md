<div align="center">

[English](./README.md) | [繁體中文](./README_zh-TW.md)

**Changelog:** see [CHANGELOG.md](./CHANGELOG.md) · **Design/Notes:** see [/updates](./updates/)

</div>

> Inspired by [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

# Claude Code Hooks Herald

Unified dispatcher + audio-only hook system for Claude Code. Herald routes every official event through a single entry point, plays local audio with throttling, and applies a configurable safety policy before tools run.

## Features

- 🛡️ **Herald dispatcher** – Single entry point (`.claude/hooks/herald.py`) for 8/9 official Claude Code events (8 implemented, PreCompact pending).
- 🧩 **BaseHook framework** – Shared validation + playback pipeline keeps individual hooks tiny and reliable.
- 🧠 **Decision API** – Allow/Deny/Ask/BlockStop responses with user overrides via `decision_policy.json`.
- 🔔 **Audio feedback** – Local `.wav` playback for notifications and completion cues.
- ⏱️ **Smart throttling** – Config-driven per-event cooldowns to prevent sound spam.
- ✅ **Claude Code Compatible** – Full support for both legacy and standard field formats (`tool_name`/`tool_input`).

## Quick Start

### Prerequisites

**System Requirements:**
- **Claude Code CLI** - [Install Claude Code](https://claude.ai/code) (this hooks system integrates with Claude Code)
- **Python 3.9+** (tested on Python 3.11-3.13)
- **uv** (ultra-fast Python package manager) - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Git** (for cloning repository)
- **Audio System:**
  - **macOS:** `afplay` (built-in)
  - **Linux:** `ffplay` (ffmpeg package) or `aplay` (alsa-utils)
  - **Windows:** `winsound` (built-in with Python)

**Install uv (if not already installed):**
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Alternative: pipx install uv
```

### Setup Steps

1. **Clone and navigate:**
   ```bash
   git clone <repository-url>
   cd claude-code-hooks-herald
   ```

2. **Provide sound files:** Place `.wav` files in `.claude/sounds/`:
   ```bash
   # Required audio files:
   # - task_complete.wav (for Stop events)
   # - agent_complete.wav (for SubagentStop events)
   # - user_prompt.wav (for Notifications)
   ```

3. **Confirm settings:** `.claude/settings.json` is pre-configured to route all events through `herald.py`. Copy to your Claude project:
   ```bash
   cp .claude/settings.json /path/to/your/claude/project/.claude/
   ```

4. **Set executable permissions:**
   ```bash
   chmod +x .claude/hooks/*.py
   ```

5. **Test installation:**
   ```bash
   # Test herald system
   echo '{"message": "test"}' | uv run .claude/hooks/herald.py --hook Notification --enable-audio

   # Test security policy
   echo '{"tool": "bash", "toolInput": {"command": "rm -rf /"}}' | uv run .claude/hooks/herald.py --hook PreToolUse
   ```

### Verification

**Expected outputs:**
- Notification test: `{"continue": true}` + audio playback
- Security test: `{"continue": false, "permissionDecision": "deny"}` (dangerous command blocked)

**Troubleshooting:**
- **No audio:**
  - Check `.claude/sounds/` directory exists with `.wav` files
  - Linux: Install audio dependencies: `sudo apt-get install ffmpeg` or `sudo apt-get install alsa-utils`
- **Permission errors:** Run `chmod +x .claude/hooks/*.py`
- **Python/uv not found:** Ensure both are in your `$PATH`
- **Claude Code not detecting hooks:** Verify `.claude/settings.json` is in your project root
- **"Module not found" errors:** Run from the repository root directory

**Platform-specific Notes:**
- **Windows:** Some antivirus software may flag Python scripts - add project directory to exclusions
- **Linux/WSL:** Ensure audio drivers are properly configured for sound playback
- **macOS:** Grant Terminal/Claude Code microphone/audio permissions if prompted

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
