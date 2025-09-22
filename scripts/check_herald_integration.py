#!/usr/bin/env python3
"""Herald update helper script.

This utility inspects the repository to ensure that herald.py, audio configuration,
and settings contain the expected registrations for the extended hook surface.
It prints a structured JSON report to stdout (to satisfy the Claude Code hook
contract) and human-readable diagnostics to stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
HERALD_PATH = REPO_ROOT / ".claude" / "hooks" / "herald.py"
AUDIO_CONFIG_PATH = REPO_ROOT / ".claude" / "hooks" / "utils" / "audio_config.json"
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"

EXPECTED_IMPORTS = {
    "from notification import NotificationHook",
    "from stop import StopHook",
    "from subagent_stop import SubagentStopHook",
    "from pre_tool_use import PreToolUseHook",
    "from post_tool_use import PostToolUseHook",
    "from user_prompt_submit import UserPromptSubmitHook",
    "from session_start import SessionStartHook",
    "from session_end import SessionEndHook",
}

EXPECTED_EVENTS = [
    "Notification",
    "Stop",
    "SubagentStop",
    "PreToolUse",
    "PostToolUse",
    "UserPromptSubmit",
    "SessionStart",
    "SessionEnd",
]

AUDIO_MAPPING_KEYS = {
    "pre_tool_use": "security_check.wav",
    "post_tool_use": "task_complete.wav",
    "user_prompt_submit": "user_prompt.wav",
    "session_start": "session_start.wav",
    "session_end": "session_complete.wav",
}


@dataclass
class CheckResult:
    passed: bool
    missing: List[str]
    detail: Dict[str, Any]


def _check_herald_imports() -> CheckResult:
    missing: List[str] = []
    detail: Dict[str, Any] = {}
    if not HERALD_PATH.exists():
        return CheckResult(False, sorted(EXPECTED_IMPORTS), {"error": "herald.py_missing"})
    try:
        text = HERALD_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return CheckResult(False, sorted(EXPECTED_IMPORTS), {"error": f"read_error:{type(exc).__name__}"})

    for item in EXPECTED_IMPORTS:
        if item not in text:
            missing.append(item)

    detail["present"] = sorted(list(EXPECTED_IMPORTS - set(missing)))
    return CheckResult(not missing, missing, detail)


def _check_handler_registration() -> CheckResult:
    missing: List[str] = []
    detail: Dict[str, Any] = {}
    if not HERALD_PATH.exists():
        return CheckResult(False, EXPECTED_EVENTS, {"error": "herald.py_missing"})
    try:
        text = HERALD_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return CheckResult(False, EXPECTED_EVENTS, {"error": f"read_error:{type(exc).__name__}"})

    for event in EXPECTED_EVENTS:
        needle = f"register_handler(\"{event}\""
        if needle not in text:
            missing.append(event)

    detail["registered"] = sorted([event for event in EXPECTED_EVENTS if event not in missing])
    return CheckResult(not missing, missing, detail)


def _check_audio_config() -> CheckResult:
    missing: List[str] = []
    detail: Dict[str, Any] = {}
    if not AUDIO_CONFIG_PATH.exists():
        return CheckResult(False, list(AUDIO_MAPPING_KEYS.keys()), {"error": "audio_config_missing"})
    try:
        config = json.loads(AUDIO_CONFIG_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        return CheckResult(False, list(AUDIO_MAPPING_KEYS.keys()), {"error": f"read_error:{type(exc).__name__}"})
    except json.JSONDecodeError as exc:
        return CheckResult(False, list(AUDIO_MAPPING_KEYS.keys()), {"error": f"parse_error:{type(exc).__name__}"})

    mappings = ((config.get("sound_files") or {}).get("mappings") or {})

    for key, expected_value in AUDIO_MAPPING_KEYS.items():
        value = mappings.get(key)
        if value != expected_value:
            missing.append(f"{key}:{expected_value}")

    detail["configured"] = {key: mappings.get(key) for key in AUDIO_MAPPING_KEYS}
    return CheckResult(not missing, missing, detail)


def _check_settings() -> CheckResult:
    missing: List[str] = []
    detail: Dict[str, Any] = {}
    if not SETTINGS_PATH.exists():
        return CheckResult(False, EXPECTED_EVENTS, {"error": "settings.json_missing"})
    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        return CheckResult(False, EXPECTED_EVENTS, {"error": f"read_error:{type(exc).__name__}"})
    except json.JSONDecodeError as exc:
        return CheckResult(False, EXPECTED_EVENTS, {"error": f"parse_error:{type(exc).__name__}"})

    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    if not isinstance(hooks, dict):
        return CheckResult(False, EXPECTED_EVENTS, {"error": "hooks_missing"})

    for event in EXPECTED_EVENTS:
        entries = hooks.get(event)
        if not entries:
            missing.append(event)
            continue
        commands = _extract_commands(entries)
        expected_cmd = f"$CLAUDE_PROJECT_DIR/.claude/hooks/herald.py --hook {event}"
        if expected_cmd not in commands:
            missing.append(event)
        detail[event] = commands

    return CheckResult(not missing, missing, detail)


def _extract_commands(entries: Any) -> List[str]:
    commands: List[str] = []
    if not isinstance(entries, list):
        return commands
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for hook in entry.get("hooks", []):
            if isinstance(hook, dict) and hook.get("type") == "command":
                cmd = hook.get("command")
                if isinstance(cmd, str):
                    commands.append(cmd)
    return commands


def _emit_summary(results: Dict[str, CheckResult]) -> None:
    messages: List[str] = ["[HeraldGuide] update_status"]
    for name, result in results.items():
        status = "ok" if result.passed else "missing"
        messages.append(f"{name}={status}")
        if result.missing:
            messages.append(f"{name}_missing={','.join(result.missing)}")
    try:
        print(" ".join(messages), file=sys.stderr)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Herald update guide")
    parser.add_argument("--json-only", action="store_true", help="Reserved for compatibility; no-op")
    parser.add_argument("--guide", action="store_true", help="Print textual guidance to stderr")
    args = parser.parse_args()

    results = {
        "imports": _check_herald_imports(),
        "handlers": _check_handler_registration(),
        "audio": _check_audio_config(),
        "settings": _check_settings(),
    }

    _emit_summary(results)

    if args.guide:
        _print_guidance()

    report = {
        "continue": True,
        "checks": {
            name: {
                "passed": result.passed,
                "missing": result.missing,
                "detail": result.detail,
            }
            for name, result in results.items()
        },
    }

    try:
        print(json.dumps(report))
    except Exception:
        print(json.dumps({"continue": True}))

    return 0


def _print_guidance() -> None:
    tips = [
        "確保 herald.py 匯入所有新增 hook 類別 (PreToolUseHook 等)",
        "在 build_default_dispatcher 中呼叫 dispatcher.register_handler 加入 8/8 事件",
        "為每個事件更新 audio_config.json 的 sound_files.mappings", 
        "在 settings.json hooks 區塊加入對應的指令路由",
        "準備對應的 .wav 音檔，避免運行時靜音",
        "更新測試與驗證腳本以涵蓋新增事件",
    ]
    try:
        for tip in tips:
            print(f"[Guide] {tip}", file=sys.stderr)
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
