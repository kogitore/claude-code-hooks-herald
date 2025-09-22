from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


HOOKS_DIR = Path(__file__).resolve().parents[1]
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

decision_module = importlib.import_module("utils.decision_api")

DecisionAPI = decision_module.DecisionAPI
DecisionResponse = decision_module.DecisionResponse


@pytest.fixture()
def decision_api() -> DecisionAPI:
    return DecisionAPI()


def test_pre_tool_use_deny_dangerous_command(decision_api: DecisionAPI) -> None:
    payload = {"command": "rm -rf /"}
    response: DecisionResponse = decision_api.pre_tool_use_decision("bash", payload)

    data = response.to_dict()
    assert data["permissionDecision"] == "deny"
    assert "permissionDecisionReason" in data
    assert data["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert response.blocked is True
    ctx = data["additionalContext"]
    assert ctx["severity"] == "critical"
    assert "system:dangerous" in ctx["tags"]
    assert response.severity == "critical"
    assert "system:dangerous" in response.tags


def test_pre_tool_use_ask_for_package_update(decision_api: DecisionAPI) -> None:
    payload = {"command": "npm install some-package"}
    response = decision_api.pre_tool_use_decision("bash", payload)
    data = response.to_dict()
    assert data["permissionDecision"] == "ask"
    assert response.blocked is True
    ctx = data["additionalContext"]
    assert ctx["severity"] == "medium"
    assert "package:install" in ctx["tags"]


def test_pre_tool_use_allow_when_no_rule_matches(decision_api: DecisionAPI) -> None:
    payload = {"command": "echo hello"}
    response = decision_api.pre_tool_use_decision("bash", payload)
    data = response.to_dict()
    assert data["permissionDecision"] == "allow"
    assert response.blocked is False
    assert data.get("additionalContext", {}).get("tags") is None


def test_post_tool_use_blocks_on_error(decision_api: DecisionAPI) -> None:
    result = {"toolError": "Command failed", "exitCode": 1}
    response = decision_api.post_tool_use_decision("bash", result)
    data = response.to_dict()
    assert data["decision"] == "block"
    assert response.blocked is True


def test_stop_decision_blocks_on_loop(decision_api: DecisionAPI) -> None:
    transcript = {"loopDetected": True}
    response = decision_api.stop_decision(transcript)
    data = response.to_dict()
    assert data["decision"] == "block"
    assert response.blocked is True


def test_stop_decision_allows_when_no_loop(decision_api: DecisionAPI) -> None:
    response = decision_api.stop_decision({})
    data = response.to_dict()
    assert data["decision"] == "allow"
    assert response.blocked is False


def test_custom_policy_extends_rules(tmp_path):
    policy = tmp_path / "policy.json"
    import json

    policy.write_text(
        json.dumps(
            {
                "pre_tool_use": {
                    "rules": [
                        {
                            "type": "command",
                            "action": "deny",
                            "pattern": r"git\s+reset\s+--hard",
                            "reason": "custom rule",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    api = DecisionAPI(policy_path=policy)
    assert any(rule.pattern.pattern == "git\\s+reset\\s+--hard" for rule in api._pre_rules)
    response = api.pre_tool_use_decision("bash", {"command": "git reset --hard"})
    data = response.to_dict()
    assert data["permissionDecision"] == "deny"
    assert data["permissionDecisionReason"] == "custom rule"


def test_tag_rule_matches_from_library(tmp_path):
    import json

    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {
                "pre_tool_use": {
                    "rules": [
                        {
                            "action": "ask",
                            "tags": ["git:destructive"],
                            "reason": "Review destructive git command",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    api = DecisionAPI(policy_path=policy)
    response = api.pre_tool_use_decision("bash", {"command": "git reset --hard"})
    data = response.to_dict()
    assert data["permissionDecision"] == "ask"
    ctx = data["additionalContext"]
    assert "git:destructive" in ctx["tags"]
    assert ctx["severity"] == "high"
