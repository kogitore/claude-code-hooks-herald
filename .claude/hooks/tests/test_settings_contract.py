"""Ensure published settings route hooks through the herald dispatcher."""
from __future__ import annotations

import json
from pathlib import Path

from common_test_utils import repo_root


def test_settings_point_to_herald_dispatcher() -> None:
    """Every hook command in settings.json should invoke the herald script."""

    settings_path = repo_root() / ".claude" / "settings.json"
    config = json.loads(settings_path.read_text(encoding="utf-8"))

    for specs in config.get("hooks", {}).values():
        for spec in specs:
            for hook in spec.get("hooks", []):
                command = hook.get("command", "")
                assert ".claude/hooks/herald.py" in command
