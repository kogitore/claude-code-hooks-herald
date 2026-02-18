<div align="center">

[English](./README.md) | [繁體中文](./README_zh-TW.md)

**Changelog:** see [CHANGELOG.md](./CHANGELOG.md) · **Design/Notes:** see [/updates](./updates/)

</div>

> Inspired by [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

# Herald Hooks

Unified hooks dispatcher for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Routes all official hook events through a single TypeScript entry point, plays local audio feedback with throttling, sends desktop notifications, and applies configurable safety policies before tools run.

## Features

- **Single dispatcher** — One entry point (`herald.ts`) for all 8 implemented Claude Code events.
- **Decision API** — Allow / Deny / Ask responses with configurable rules via `decision-policy.json`.
- **Audio feedback** — Local `.wav` playback with per-event throttling. Supports multiple files per event with random selection.
- **Desktop notifications** — macOS / Linux / Windows with i18n message support.
- **Terminal title** — Updates terminal/iTerm2 tab title to show current event status.
- **Session tracking** — File-based state management and JSONL event logging.
- **CLI controls** — `toggle`, `pause`, `resume`, `status`, `preview` commands.
- **Zero dependencies** — Runs on Bun built-ins only (`fs`, `path`, `child_process`).

## Quick Start

### Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- [Bun](https://bun.sh/) runtime

**Audio system (for sound playback):**
- **macOS:** `afplay` (built-in)
- **Linux:** `ffplay` (ffmpeg) or `aplay` (alsa-utils)
- **Windows:** PowerShell `[System.Media.SoundPlayer]` (built-in)

### Install

```bash
git clone https://github.com/user/herald-hooks.git
cd herald-hooks
```

Then copy the hook settings into your Claude Code project:

```bash
cp .claude/settings.json /path/to/your/project/.claude/settings.json
```

> Alternatively, merge the `hooks` key from `.claude/settings.json` into your existing settings file.

### Add Sound Files

Place your `.wav` files in `.claude/sounds/`:

```
.claude/sounds/
├── task_complete.wav    # Stop / PostToolUse / SessionEnd
├── agent_complete.wav   # SubagentStop
└── user_prompt.wav      # Notification / PreToolUse / SessionStart / UserPromptSubmit
```

See `.claude/sounds/README.md` for details and examples.

### Verify

```bash
# Test notification
echo '{"message": "test"}' | bun run .claude/hooks/herald.ts --hook Notification

# Test security policy (should be denied)
echo '{"tool": "Bash", "input": {"command": "rm -rf /"}}' | bun run .claude/hooks/herald.ts --hook PreToolUse
```

**Expected output:**
- Notification: `{"continue":true}` + audio playback
- Security: `{"continue":false, ...}` (dangerous command blocked)

## Configuration

### Audio (`config/audio.json`)

```json
{
  "sound_files": {
    "base_path": "./.claude/sounds",
    "mappings": {
      "Stop": ["task_complete.wav"],
      "SubagentStop": ["agent_complete.wav"],
      "Notification": ["user_prompt.wav"]
    }
  },
  "audio_settings": {
    "volume": 0.2,
    "throttle_seconds": {
      "Stop": 120,
      "Notification": 30
    }
  }
}
```

Override sound directory via environment variable:

```bash
export CLAUDE_SOUNDS_DIR="/absolute/path/to/sounds"
```

### Decision Policy (`config/decision-policy.json`)

Safety rules for PreToolUse / PostToolUse / Stop events:

```json
{
  "pre_tool_use": {
    "rules": [
      {
        "action": "deny",
        "pattern": "rm\\s+-rf\\s+/",
        "reason": "Dangerous: delete root directory",
        "tags": ["system:dangerous"],
        "severity": "critical"
      },
      {
        "action": "ask",
        "tags": ["git:destructive"],
        "reason": "Confirm before wiping all changes",
        "severity": "high"
      }
    ]
  }
}
```

**Built-in tags:**

| Tag | Description | Severity |
|-----|-------------|----------|
| `system:dangerous` | Destructive commands (`rm -rf /`, `shutdown`) | critical |
| `git:destructive` | State-resetting git commands (`reset --hard`, `clean -fd`) | high |
| `secrets:file` | Credential files (`.env`, `id_rsa`, `*.pem`) | high |
| `package:install` | Package installs (`npm install`, `pip install`) | medium |
| `dependency:lock` | Lock files (`package-lock.json`, `poetry.lock`) | medium |

### i18n Messages (`config/messages.json`)

Customize notification messages per locale:

```json
{
  "locale": "zh-TW",
  "messages": {
    "Stop": "任務完成",
    "SubagentStop": "子代理完成",
    "Notification": "收到通知",
    "SessionEnd": "工作階段結束"
  }
}
```

## CLI

```bash
bun run .claude/hooks/herald.ts toggle            # Toggle mute on/off
bun run .claude/hooks/herald.ts pause             # Mute all sounds
bun run .claude/hooks/herald.ts resume            # Unmute sounds
bun run .claude/hooks/herald.ts status            # Show current state
bun run .claude/hooks/herald.ts preview [event]   # Play sample sound
```

## Supported Events

| Event | Description |
|-------|-------------|
| `Notification` | General notification |
| `Stop` | Task completed |
| `SubagentStop` | Sub-agent completed |
| `PreToolUse` | Security gate before tool execution |
| `PostToolUse` | Audit after tool execution |
| `UserPromptSubmit` | Prompt validation and rate limiting |
| `SessionStart` | Session initialization and health checks |
| `SessionEnd` | Cleanup and state finalization |

> `PreCompact` is defined but not yet implemented.

## Testing

```bash
bun test
```

Tests use `AUDIO_PLAYER_CMD=true` (no-op) so they don't require system audio.

## Project Structure

```
.claude/
├── hooks/
│   ├── herald.ts              # Main dispatcher
│   ├── lib/                   # Core libraries
│   │   ├── audio.ts           # Audio playback + throttling
│   │   ├── notify.ts          # Desktop notifications + terminal title
│   │   ├── decision.ts        # Safety evaluation
│   │   ├── cli.ts             # CLI commands
│   │   ├── session.ts         # Session state + event logging
│   │   ├── constants.ts       # Event type constants
│   │   └── types.ts           # Type definitions
│   ├── handlers/              # Event-specific handlers
│   ├── config/                # JSON configuration files
│   └── tests/                 # Test suite
├── sounds/                    # Audio files (.wav)
├── logs/                      # Runtime logs and session data
└── settings.json              # Claude Code hook routing
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No audio | Check `.claude/sounds/` has `.wav` files |
| Linux no audio | `sudo apt-get install ffmpeg` or `alsa-utils` |
| Hooks not detected | Ensure `.claude/settings.json` is in your project root |
| Bun not found | [Install Bun](https://bun.sh/) and ensure it's in `$PATH` |

## Disclaimer

This is an independent, community-driven project and is **not affiliated with, endorsed by, or officially supported by Anthropic, PBC**. "Claude" and "Claude Code" are trademarks of Anthropic. This project integrates with Claude Code's public [hooks API](https://docs.anthropic.com/en/docs/claude-code/hooks).

## License

[MIT](./LICENSE)

## Acknowledgments

Inspired by Claude Code's hook system and the [claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) project.
