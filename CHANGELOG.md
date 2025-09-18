# Changelog

All notable changes to this project will be documented in this file. The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and adheres to [Semantic Versioning](https://semver.org/).

Commit messages are recommended to follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## [Unreleased]
### Added
- Support additional official hook event types
- Audio layering and custom sound file support
- More platform audio backends (PulseAudio, ALSA)
- Established bilingual `/updates` document structure and index

### Changed
- Tuned default volume and throttling strategy
- Improved cross-platform audio backend selection logic

### Fixed
- Provide clearer error messages when audio files are missing
- Improve stability of Windows volume control

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
