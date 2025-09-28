# Hook Tests (moved to tests/)

This folder contains lightweight, black-box tests for the three audio hooks in `.claude/hooks`:

- `notification.py`
- `stop.py`
- `subagent_stop.py`

## Run All Tests

```
uv run .claude/hooks/tests/run_tests.py
```

Optional demo to verify local audio playback (macOS `afplay`):

```
uv run .claude/hooks/tests/run_tests.py --demo-sound --sounds ./.claude/sounds
```

Notes:
- Current hooks are placeholders, so results show as `PENDING` until the hooks emit audio or success markers.
- The tests feed a minimal JSON payload on stdin to each hook, mirroring how Claude Code hooks receive events.
- When the hooks are implemented, consider printing a short line like `AUDIO:notification` or echoing the provided `marker` to allow the tests to assert `PASS` deterministically.
