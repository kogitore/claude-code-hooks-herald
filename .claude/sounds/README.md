# Sound Files

This directory is for user-provided sound files for the **Claude Code Hooks** project. By default, no copyrighted sounds are included.

## Placement Rules

Place your `.wav` files directly in this directory. The hook system is configured to look for the following specific filenames (placeholders ending with `.example` are provided—rename or adjust config to use real files):

- `user_prompt.wav.example` → rename to `user_prompt.wav` (or update mapping) - Played for general user notifications.
- `task_complete.wav` - Played when a task is successfully completed.
- `agent_complete.wav` - Played when a sub-agent's task is completed.

For best results, it is recommended to use 16-bit PCM `.wav` files, between 0.1–1.5 seconds in length, and smaller than 50 KB.

## Configuration

The mapping between hook events and sound files is configured in `.claude/hooks/utils/audio_config.json`. You can change which sound plays for which event without modifying the hook source code.

## Using an External Directory (Optional)

You can override the default sounds directory by setting the `CLAUDE_SOUNDS_DIR` environment variable (e.g., `export CLAUDE_SOUNDS_DIR=/path/to/my_sounds`). This is useful for managing a large library of sounds outside the Git repository.

## Copyright

Please do not commit copyrighted sound files to this repository. It is recommended to use public domain (CC0) or self-made/licensed sounds.
