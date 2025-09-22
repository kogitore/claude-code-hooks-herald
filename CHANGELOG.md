# Changelog

All notable changes to this project will be documented in this file. The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and adheres to [Semantic Versioning](https://semver.org/).

Commit messages are recommended to follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## [Unreleased]
### Added
- Herald dispatcher (`.claude/hooks/herald.py`) with Decision API integration for Pre/PostToolUse and Stop events.
- BaseHook framework plus Notification/Stop/SubagentStop implementations that reuse shared audio handling.
- Configurable `decision_policy.json` (with `decision_policy.example.json` template + ADR 0003) to extend allow/deny/ask/block rules without losing built-in safeguards.
- TagMatcher library (`system:dangerous`, `package:install`, `git:destructive`, etc.) with severity ranking for policy responses; ADR 0004 documents the design.
- End-to-end tests covering dispatcher routing, settings.json wiring, and decision policy outcomes.

### Changed
- `.claude/settings.json` now routes all official events through the Herald dispatcher.
- README (EN/繁中) updated to describe dispatcher architecture, Decision API, and CLI usage.
- Roadmap v1.3 Phase 1 tasks marked completed for dispatcher, BaseHook, Decision API, and migration work.

### Fixed
- Ensured CLI hooks emit minimal JSON (`{"continue": true}`) while telemetry stays on stderr.

---

## [0.1.0] - 2025-09-18
### Added
- **Notification sounds**: play audio cues for user prompts/notifications
- **Task completion sounds**: dedicated audio for tool/task completion
- **Subagent completion sounds**: separate audio for subagent success
- **Smart throttling**: timestamp-based cache to avoid audio spam
- **Local audio files**: operate purely on local `.wav` assets, no API keys required
- **Cross-platform support**: macOS (afplay), Linux (ffplay/aplay), Windows (winsound)
- **Volume control**: macOS/Linux via player args, Windows via in-memory processing
- **Configuration system**: `.claude/hooks/utils/audio_config.json` manages volume, paths, mappings
- **Testing framework**: `uv run` + `pytest` scripts with `AUDIO_PLAYER_CMD` override

### Audio
- Default sound mappings: `task_complete.wav` (Stop), `agent_complete.wav` (SubagentStop), `user_prompt.wav` (Notification)
- Throttle windows: Stop/SubagentStop (120s), Notification (30s)
- Default volume: 0.2 (20%)

### Platform Support
- **Windows**: Python stdlib `winsound` + `audioop` for volume scaling
- **macOS**: `afplay` CLI with `-v` volume parameter
- **Linux**: supports `ffplay` (`-volume`) and `aplay`

[0.1.0]: https://github.com/kogitore/claude-code-hooks-herald
