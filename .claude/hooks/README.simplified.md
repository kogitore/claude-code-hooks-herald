# Simplified Hooks (Audio-only)

This directory includes minimal hooks that follow Claude Code's JSON contract and focus on audio feedback only.

- utils/simple_audio_manager.py — tiny, robust player using macOS afplay
- utils/simple_constants.py — minimal event constants
- simple_notification.py — Notification hook
- simple_stop.py — Stop and SubagentStop hooks

Run examples (stdin JSON required, but content is ignored beyond contract):

```bash
# Notification
echo '{"hook_event_name":"Notification","message":"hi"}' | ./.claude/hooks/simple_notification.py

# Stop
echo '{"hook_event_name":"Stop"}' | ./.claude/hooks/simple_stop.py Stop

# SubagentStop
echo '{"hook_event_name":"SubagentStop"}' | ./.claude/hooks/simple_stop.py SubagentStop
```

All scripts are safe to fail silently and always emit a valid JSON response with `{ "continue": true }`.
