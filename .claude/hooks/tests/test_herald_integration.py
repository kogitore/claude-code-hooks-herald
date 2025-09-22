from __future__ import annotations

import json
from common_test_utils import repo_root, run_hook


def _invoke(event: str, payload: dict) -> tuple[dict, str]:
    result = run_hook(
        script_relpath=".claude/hooks/herald.py",
        payload=payload,
        args=["--hook", event],
    )
    assert result.returncode == 0
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    assert lines, "herald output should contain JSON"
    return json.loads(lines[-1]), result.stderr


def test_pre_tool_use_deny_dangerous_command():
    payload = {
        "tool": "bash",
        "toolInput": {
            "command": "rm -rf /"
        }
    }
    data, _ = _invoke("PreToolUse", payload)
    assert data["permissionDecision"] == "deny"
    assert "permissionDecisionReason" in data


def test_pre_tool_use_allow_safe_command():
    payload = {
        "tool": "bash",
        "toolInput": {
            "command": "echo hello"
        }
    }
    data, _ = _invoke("PreToolUse", payload)
    assert data["permissionDecision"] == "allow"


def test_stop_blocks_on_loop_detected():
    payload = {"loopDetected": True}
    data, _ = _invoke("Stop", payload)
    assert data["decision"] == "block"


def test_subagent_stop_allows_when_no_loop():
    payload = {"status": "SubagentComplete"}
    data, _ = _invoke("SubagentStop", payload)
    assert data.get("decision", "allow") == "allow"


def test_precompact_noop_response():
    data, stderr = _invoke("PreCompact", {"phase": "compact"})
    assert data["continue"] is True
    assert "permissionDecision" not in data
    assert "decision" not in data
    assert "PreCompact" in stderr


def test_settings_route_to_herald():
    settings_path = repo_root() / ".claude" / "settings.json"
    config = json.loads(settings_path.read_text(encoding="utf-8"))
    for specs in config.get("hooks", {}).values():
        for spec in specs:
            for hook in spec.get("hooks", []):
                command = hook.get("command", "")
                assert ".claude/hooks/herald.py" in command
