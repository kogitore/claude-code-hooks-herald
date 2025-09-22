# Changelog

All notable changes to this project will be documented in this file. The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and adheres to [Semantic Versioning](https://semver.org/).

Commit messages are recommended to follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## [Unreleased]

## [0.2.0] - 2025-09-22
### Added
- **Complete Claude Code Events Support**: 8/9 official events implemented (UserPromptSubmit, PreToolUse, PostToolUse, SessionStart, SessionEnd)
- **Claude Code Field Compatibility**: Full support for both legacy (`tool`/`toolInput`) and standard (`tool_name`/`tool_input`) field formats
- **Comprehensive Test Suite**: Enhanced test coverage with 9 passing tests including field precedence and error handling scenarios
- **Decision API Security**: Advanced security policies with command pattern matching, file protection, and package installation validation
- Herald dispatcher (`.claude/hooks/herald.py`) with Decision API integration for Pre/PostToolUse and Stop events.
- BaseHook framework plus Notification/Stop/SubagentStop implementations that reuse shared audio handling.
- Configurable `decision_policy.json` (with `decision_policy.example.json` template + ADR 0003) to extend allow/deny/ask/block rules without losing built-in safeguards.
- TagMatcher library (`system:dangerous`, `package:install`, `git:destructive`, etc.) with severity ranking for policy responses; ADR 0004 documents the design.

### Changed
- **Field Extraction Logic**: Enhanced `_extract_tool()` and `_extract_tool_input()` methods to support Claude Code standard field names
- **Test Infrastructure**: Added direct hook testing utilities (`_invoke_pre_tool_use_direct`) and decision parsing helpers
- **Roadmap Corrections**: Updated roadmap v1.6 to reflect actual 8/9 event completion status and removed non-official Error event
- `.claude/settings.json` now routes all official events through the Herald dispatcher.
- README (EN/繁中) updated to describe dispatcher architecture, Decision API, and CLI usage.

### Fixed
- **Critical Tool Blocking Issue**: Resolved Claude Code field name mismatch that caused tools to be incorrectly blocked even when permitted
- **JSON Output Format**: Ensured full compliance with Claude Code hook schema requirements
- **Error Handling**: Graceful degradation for invalid JSON inputs while maintaining hook functionality
- Ensured CLI hooks emit minimal JSON (`{"continue": true}`) while telemetry stays on stderr.

### Security
- **Enhanced PreToolUse Security**: Added pattern matching for dangerous commands (`rm -rf`, `shutdown`, etc.)
- **Sensitive File Protection**: Automatic detection and blocking of operations on `.env`, key files, and credentials
- **Package Installation Guards**: Human confirmation required for `npm install`, `pip install`, and similar operations

### Removed
- **Non-Official Event Support**: Removed Error event implementation to comply with Claude Code official specification (9 events only)

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
