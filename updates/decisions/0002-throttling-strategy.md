---
id: 0002
status: accepted
date: 2025-09-18
related: []
---

> **[中文版本](./0002-throttling-strategy_zh-TW.md)**

# Decision: Audio Throttling Strategy

## Context
- Active Claude Code sessions can trigger identical events repeatedly, creating distracting audio spam.
- Hooks must remain lightweight and stateless across invocations, so we cannot rely on in-process caches.

## Options Considered
1. **In-memory throttle cache** — simple but resets each invocation and fails across concurrent hooks.
2. **External store (Redis/SQLite)** — durable yet adds heavy dependencies.
3. **Filesystem-based JSON cache** — lightweight, easy to inspect, works across processes.

## Decision
Implement a time-window throttle using a JSON cache stored at `logs/audio_throttle.json`.
- `Stop` / `SubagentStop`: 120-second window keyed by event name.
- `Notification`: 30-second window keyed by `Notification:{sha1(message)[:12]}` so distinct messages still play.
- Writes use atomic temp-file swaps plus `fcntl` locks on POSIX to avoid corruption.

## Consequences
- **Positive**: greatly reduces repetitive playback; no extra services; cache can be cleared manually.
- **Trade-offs**: adds disk I/O and requires lock handling; JSON grows over long sessions and needs rotation.

## Implementation Notes
- `AudioManager.should_throttle()` exposes the window logic.
- Use `pathlib.Path` to resolve `logs/` alongside the project root.
- Provide graceful degradation: if locking fails, log a warning and proceed without throttling.

## References
- `.claude/hooks/utils/audio_manager.py`
- `.claude/hooks/tests/test_throttle.py`
- `logs/audio_throttle.json` (runtime artifact)
