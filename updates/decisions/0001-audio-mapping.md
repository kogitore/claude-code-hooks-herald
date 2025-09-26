---
id: 0001
status: accepted
date: 2025-09-18
related: []
---

> **[中文版本](./0001-audio-mapping_zh-TW.md)**

# Decision: Audio Mapping Strategy

## Context
- Claude Code triggers a limited set of official events (`Stop`, `SubagentStop`, `Notification`).
- Each event needs an audio cue without hard-coding paths in Python scripts.
- We must stay extensible for future events while preserving backward compatibility with legacy key names.

## Options Considered
1. **Hard-code mappings in Python** — minimal setup but difficult to override per project.
2. **Filename convention (`stop.wav`, etc.)** — simple yet ambiguous when multiple variants exist.
3. **External configuration file (JSON/YAML)** — keeps code lean and enables user overrides.

## Decision
Adopt a JSON configuration file (`.claude/hooks/utils/audio_config.json`) that maps official event names to semantic sound file names. The loader normalizes aliases (`stop`, `agent-stop`, etc.) to canonical keys and falls back from `SubagentStop` to `Stop` when needed.

## Consequences
- **Positive**: clear separation of config vs. code; users can swap audio assets safely; supports aliasing for older names.
- **Trade-offs**: configuration adds a layer of complexity and requires missing-file handling at runtime.

## Implementation Notes
- `AudioManager` loads `audio_config.json` and resolves sound paths under `.claude/sounds/` by default.
- `_canonical_audio_key()` handles case/alias normalization.
- Fallback chain: `SubagentStop → Stop` ensures continuity when custom files are absent.
- Unit tests cover canonicalization and error logging via `.claude/hooks/tests/test_notification.py` etc.

## References
- `.claude/hooks/utils/audio_config.json`
- `.claude/hooks/utils/audio_manager.py`
- `.claude/hooks/tests/test_audio_played_and_timeout.py`
