<div align="center">

[English](./README.md) | [繁體中文](./README_zh-TW.md)

**Changelog:** see [CHANGELOG.md](./CHANGELOG.md) · **Documentation:** see [/docs](./docs/)

</div>

> Inspired by [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) and [claude-code-infrastructure-showcase](https://github.com/diet103/claude-code-infrastructure-showcase)

# Claude Code Hooks Herald

Unified hooks system and toolkit for Claude Code. Herald provides audio notifications, Notion project management, skill auto-activation, and configurable security policies — all through a single dispatcher.

## Features

- 🛡️ **Herald Dispatcher** – Single entry point (`.claude/herald/dispatcher.py`) for all 8 official Claude Code events
- 🔔 **Audio Feedback** – Local `.wav` playback for notifications and completion cues with smart throttling
- 📋 **Notion Integration** – Project/task management with auto-detection (uses folder name as project)
- 🧠 **Skill Auto-Activation** – Suggests relevant skills based on prompt content (supports Traditional Chinese)
- ⚡ **Slash Commands** – `/notion-sync`, `/notion-task` for quick operations
- 🔒 **Security Policy** – Allow/Deny/Ask/BlockStop responses with customizable rules
- ✅ **Claude Code Compatible** – Full support for both legacy and standard field formats

## Project Structure

```
.claude/
├── commands/           # Slash commands (/notion-sync, /notion-task)
├── herald/             # Herald toolkit (unified dispatcher)
│   ├── dispatcher.py   # Single entry point for all hooks
│   ├── handlers/       # Individual hook handlers
│   ├── utils/          # Shared utilities (audio, config, decision API)
│   ├── config/         # Audio and policy configuration
│   ├── notion/         # Notion API integration
│   ├── tests/          # Test suite
│   └── dev-tools/      # Development utilities
├── skills/             # Skill definitions & auto-activation rules
│   └── skill-rules.json
└── sounds/             # Audio files (.wav)
    └── default/        # Default sound pack
```

## Quick Start

### Prerequisites

**System Requirements:**
- **Claude Code CLI** - [Install Claude Code](https://claude.ai/code)
- **Python 3.10+** (tested on Python 3.11-3.14)
- **uv** (ultra-fast Python package manager) - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Git** (for cloning repository)
- **Audio System:**
  - **macOS:** `afplay` (built-in)
  - **Linux:** `ffplay` (ffmpeg) or `aplay` (alsa-utils)
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

2. **Provide sound files:** Place `.wav` files in `.claude/sounds/default/`:
   ```bash
   # Required audio files:
   # - task_complete.wav (for Stop events)
   # - agent_complete.wav (for SubagentStop events)
   # - user_prompt.wav (for Notifications)
   ```

3. **Run the interactive installer:**
   ```bash
   python3 install.py
   ```

   The installer will:
   - Ask for your preferred **volume** (0-100%)
   - Ask for optional **quiet hours** (e.g., 22:00-08:00 for no audio at night)
   - Write settings to `.claude/settings.json` (preserves existing settings)
   - Create a backup of any existing settings file

   **Example session:**
   ```
   【音量設定】
   請輸入音量 (0-100) [預設: 30]: 50

   【靜音時段設定】
   是否要設定靜音時段? (y/N): y
   請輸入靜音開始時間 [範例: 22:00]: 22:00
   請輸入靜音結束時間 [範例: 08:00]: 08:00

   設定摘要:
     音量: 50%
     靜音時段: 22:00 - 08:00
   ```

4. **Set executable permissions:**
   ```bash
   chmod +x .claude/herald/dispatcher.py
   ```

5. **Test installation:**
   ```bash
   # Test herald system
   echo '{"message": "test"}' | uv run .claude/herald/dispatcher.py --hook Notification

   # Test security policy
   echo '{"tool": "bash", "toolInput": {"command": "rm -rf /"}}' | uv run .claude/herald/dispatcher.py --hook PreToolUse
   ```

### Verification

**Expected outputs:**
- Notification test: `{"continue": true}` + audio playback
- Security test: `{"continue": false, "permissionDecision": "deny"}` (dangerous command blocked)

**Troubleshooting:**
- **No audio:**
  - Check `.claude/sounds/default/` directory exists with `.wav` files
  - Linux: Install audio dependencies: `sudo apt-get install ffmpeg` or `sudo apt-get install alsa-utils`
- **Permission errors:** Run `chmod +x .claude/herald/dispatcher.py`
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

**Quick start:** copy `.claude/hooks/utils/decision_policy.example.json` to `decision_policy.json`, remove the sections you do not need, then adjust regex patterns/reasons. The template documents common scenarios (package installs, git resets, credential files) and defaults to `allow` when no rule matches. See [docs/adr/0003-decision-policy-template.md](./docs/adr/0003-decision-policy-template.md) for full guidance.

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

## Notion Integration

Herald includes a complete Notion project/task management system. Project names are auto-detected from your folder name.

### Setup

1. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Copy `.env.example` to `.env` and configure:
   ```bash
   NOTION_API_TOKEN=secret_xxx
   NOTION_PROJECT_DATABASE_ID=xxx   # Your projects database
   NOTION_TASK_DATABASE_ID=xxx      # Your tasks database
   ```
3. Share your Notion databases with the integration

### CLI Usage

```bash
# Check current project status
uv run python .claude/herald/notion/cli.py project info

# Create/get project in Notion (auto-detects name from folder)
uv run python .claude/herald/notion/cli.py project create

# List tasks
uv run python .claude/herald/notion/cli.py tasks list

# Create task interactively
uv run python .claude/herald/notion/cli.py tasks create
```

### Slash Commands

- **`/notion-sync`** – Sync current project to Notion
- **`/notion-task 實作登入功能`** – Quick task creation with type inference

### Python API

```python
import sys
sys.path.insert(0, ".claude/herald")

from notion import NotionClient, ProjectManager, TaskManager
from notion.tasks import TaskDefinition, TaskPriority

with NotionClient() as client:
    pm = ProjectManager(client)
    project_id, created = pm.get_or_create_project()

    tm = TaskManager(client, pm)
    task = TaskDefinition(name="新功能", priority=TaskPriority.HIGH)
    tm.create_task(task, project_id)
```

## Skill Auto-Activation

Skills are automatically suggested based on prompt content. Configure triggers in `.claude/skills/skill-rules.json`:

```json
{
  "skills": {
    "test": {
      "priority": "high",
      "promptTriggers": {
        "keywords": ["pytest", "unittest", "測試"],
        "intentPatterns": ["(run|execute).*?test"]
      }
    }
  }
}
```

Built-in skills: `test`, `refactor`, `debug`, `review`, `docs`, `hooks`, `notion-integration`, `security`

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

This project was inspired by:
- [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) - Original hooks patterns
- [diet103/claude-code-infrastructure-showcase](https://github.com/diet103/claude-code-infrastructure-showcase) - Skill auto-activation pattern
- [Anthropic Engineering Blog](https://www.anthropic.com/engineering/claude-code-best-practices) - Best practices for Claude Code

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
