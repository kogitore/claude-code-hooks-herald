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


def _invoke_pre_tool_use_direct(payload: dict) -> dict:
    result = run_hook(
        script_relpath=".claude/hooks/pre_tool_use.py",
        payload=payload,
    )
    assert result.returncode == 0
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    assert lines, "pre_tool_use output should contain JSON"
    return json.loads(lines[-1])


def _pretool_decision(data: dict) -> str:
    hook_payload = data.get("hookSpecificOutput") or {}
    return hook_payload.get("permissionDecision") or data.get("permissionDecision")


def _pretool_reason(data: dict) -> str | None:
    hook_payload = data.get("hookSpecificOutput") or {}
    return hook_payload.get("permissionDecisionReason") or data.get("permissionDecisionReason")


def test_pre_tool_use_deny_dangerous_command():
    payload = {
        "tool": "bash",
        "toolInput": {
            "command": "rm -rf /"
        }
    }
    data, _ = _invoke("PreToolUse", payload)
    assert _pretool_decision(data) == "deny"
    assert _pretool_reason(data)


def test_pre_tool_use_allow_safe_command():
    payload = {
        "tool": "bash",
        "toolInput": {
            "command": "echo hello"
        }
    }
    data, _ = _invoke("PreToolUse", payload)
    assert _pretool_decision(data) == "allow"


def test_pre_tool_use_accepts_claude_code_field_names():
    payload = {
        "tool_name": "Read",
        "tool_input": {
            "file_path": "/tmp/test.txt"
        }
    }
    data, _ = _invoke("PreToolUse", payload)
    assert _pretool_decision(data) == "allow"
    assert data["continue"] is True


def test_pre_tool_use_field_precedence_prefers_legacy_tool_key():
    payload = {
        "tool": "LegacyPreferred",
        "tool_name": "ShouldBeIgnored",
        "tool_input": {
            "args": ["--dry-run"]
        }
    }
    data = _invoke_pre_tool_use_direct(payload)
    assert _pretool_decision(data) == "allow"
    context = data.get("additionalContext") or {}
    assert context.get("tool") == "LegacyPreferred"


def test_pre_tool_use_invalid_tool_input_downgrades_to_manual_review():
    payload = {
        "tool_name": "bash",
        "tool_input": "{not-json",
    }
    data, _ = _invoke("PreToolUse", payload)
    assert _pretool_decision(data) == "ask"
    assert data["continue"] is False
    reason = _pretool_reason(data)
    assert reason is not None
    direct = _invoke_pre_tool_use_direct(payload)
    issues = (direct.get("additionalContext") or {}).get("issues", [])
    assert "invalid_tool_input_json" in issues


def test_stop_blocks_on_loop_detected():
    payload = {"loopDetected": True}
    data, stderr = _invoke("Stop", payload)
    assert "decision=block" in stderr
    assert "blocked=True" in stderr
    assert data["continue"] is True


def test_subagent_stop_allows_when_no_loop():
    payload = {"status": "SubagentComplete"}
    data, stderr = _invoke("SubagentStop", payload)
    assert "decision=approve" in stderr
    assert data["continue"] is True


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
