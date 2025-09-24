#!/usr/bin/env python3
"""Decision API helper for Claude Code hooks.

This module centralises allow/deny/ask/block decisions for different hook
events. It loads optional policy configuration from
`.claude/hooks/utils/decision_policy.json` (if present) and falls back to a
conservative built-in defaults that prioritise safety while keeping UX simple.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config_manager import ConfigManager


_DEFAULT_POLICY = {
    "pre_tool_use": {
        "rules": [
            {
                "type": "command",
                "action": "deny",
                "pattern": r"rm\s+-rf\s+(?:/|\$HOME|\$CLAUDE_PROJECT_DIR)",
                "reason": "偵測到危險的 rm -rf 指令",
                "tags": ["system:dangerous"],
                "severity": "critical",
            },
            {
                "type": "command",
                "action": "deny",
                "pattern": r"shutdown\b|halt\b|reboot\b",
                "reason": "偵測到系統關機或重啟指令",
                "tags": ["system:dangerous"],
                "severity": "critical",
            },
            {
                "type": "command",
                "action": "ask",
                "pattern": r"pip\s+install|npm\s+install|uv\s+pip",
                "reason": "安裝依賴需要人工確認",
                "tags": ["package:install"],
                "severity": "medium",
            },
            {
                "type": "path",
                "action": "deny",
                "pattern": r"\.env(\.|$)|id_rsa|id_ed25519",
                "reason": "偵測到敏感憑證或環境變數檔案",
                "tags": ["secrets:file"],
                "severity": "high",
            },
            {
                "type": "path",
                "action": "ask",
                "pattern": r"(package\.json|poetry\.lock|requirements\.txt)$",
                "reason": "修改依賴定義文件需要確認",
                "tags": ["dependency:lock"],
                "severity": "medium",
            },
        ],
    },
    "post_tool_use": {
        "block_on_error": True,
        "error_keys": ["toolError", "error", "traceback"],
        "block_exit_codes_at_least": 1,
    },
    "stop": {
        "block_on_loop": True,
    },
}


_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


@dataclass
class SimpleRule:
    type: str
    action: str
    pattern: re.Pattern
    reason: str
    severity: str = 'medium'


# 簡化的內建危險命令模式 - 直接定義，無需複雜抽象化
_DANGEROUS_PATTERNS = {
    'system_destructive': r"(?:^|[;&|]\s*)(?:rm\s+-rf\s+(?:/|~|\$HOME)|shutdown|halt|reboot)\b",
    'package_management': r"(?:^|[;&|]\s*)(?:npm|pnpm|yarn|pip|poetry|uvx?)\s+(?:install|add|update|uninstall|remove)\b",
    'git_destructive': r"(?:^|[;&|]\s*)git\s+(?:reset\s+--hard|clean\s+-fd|checkout\s+--|restore\s+--source)\b",
}


# TagMatcher 移除 - 使用簡化的內聯匹配邏輯


@dataclass
class DecisionResponse:
    payload: Dict[str, Any]
    blocked: bool = False
    severity: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.payload


# _CompiledRule 移除 - 使用 SimpleRule 替代


class DecisionAPI:
    def __init__(self, config_manager: Optional[ConfigManager] = None, policy_path: Optional[Path] = None) -> None:
        # 優先使用傳入的 config_manager
        self.config_manager = config_manager or ConfigManager.get_instance()
        self.policy_path = policy_path or self._default_policy_path()
        
        # 簡化的政策載入
        self.policy = self._load_simple_policy()
        
        # 編譯簡化的規則
        self._compiled_rules: List[SimpleRule] = self._compile_rules(
            self.policy.get("pre_tool_use", {}).get("rules", [])
        )

    # -- Public decision helpers -----------------------------------------
    def pre_tool_use_decision(self, tool_name: str, tool_input: Optional[Dict[str, Any]]) -> DecisionResponse:
        command_blob = self._extract_command(tool_input)
        paths = self._extract_paths(tool_input)
        context_base = {"tool": tool_name}

        for rule in self._compiled_rules:
            if rule.type == "command" and command_blob:
                if rule.pattern.search(command_blob):
                    return self._build_simple_response(rule, context_base, command_blob)
            elif rule.type == "path" and paths:
                matched_path = self._match_path(rule.pattern, paths)
                if matched_path:
                    return self._build_simple_response(rule, context_base, matched_path)

        return self.allow(event="PreToolUse", additional_context=context_base)

    def post_tool_use_decision(self, tool_name: str, result: Optional[Dict[str, Any]]) -> DecisionResponse:
        result = result or {}
        context = {"tool": tool_name}

        if self.policy.get("post_tool_use", {}).get("block_on_error", False):
            if self._has_error(result):
                reason = result.get("toolError") or result.get("error") or "工具執行失敗"
                context["matched"] = "error"
                return self.block(reason, event="PostToolUse", additional_context=context)

            exit_code = self._extract_exit_code(result)
            threshold = int(self.policy.get("post_tool_use", {}).get("block_exit_codes_at_least", 1))
            if exit_code is not None and exit_code >= threshold:
                context["matched"] = "exitCode"
                context["exitCode"] = exit_code
                return self.block(f"工具回傳非零代碼 {exit_code}", event="PostToolUse", additional_context=context)

        return self.allow(event="PostToolUse", additional_context=context)

    def stop_decision(self, transcript: Optional[Dict[str, Any]]) -> DecisionResponse:
        transcript = transcript or {}
        context: Dict[str, Any] = {}

        if self.policy.get("stop", {}).get("block_on_loop", False):
            if self._is_loop_detected(transcript):
                context["matched"] = "loopDetected"
                return self.block_stop("偵測到 stop 迴圈，已阻擋重複觸發", additional_context=context)

        return self.allow_stop(additional_context=context)

    # -- Primitive builders ------------------------------------------------
    def allow(
        self,
        *,
        event: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        return self._build_response('allow', event=event, **(additional_context or {}))

    def deny(
        self,
        reason: str,
        *,
        event: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        return self._build_response('deny', reason=reason, event=event, **(additional_context or {}))

    def ask(
        self,
        reason: str,
        *,
        event: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        return self._build_response('ask', reason=reason, event=event, **(additional_context or {}))

    def block(
        self,
        reason: str,
        *,
        event: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        return self._build_response('block', reason=reason, event=event, **(additional_context or {}))

    def block_stop(
        self,
        reason: str,
        *,
        additional_context: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        return self.block(
            reason,
            event="Stop",
            additional_context=additional_context,
            severity=severity,
            tags=tags,
        )

    def allow_stop(
        self,
        *,
        additional_context: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        return self._build_response('approve', event='Stop', **(additional_context or {}))

    # -- Internal helpers -------------------------------------------------
    def _build_response(self, action: str, reason: str = None, 
                       event: str = None, blocked: bool = False, **context) -> DecisionResponse:
        """\u7d71\u4e00\u7684\u56de\u61c9\u5efa\u69cb\u5668 - \u5408\u4f75\u6240\u6709\u56de\u61c9\u985e\u578b"""
        if action == 'allow':
            payload = {"permissionDecision": "allow"}
        elif action in ['deny', 'ask']:
            payload = {"permissionDecision": action, "permissionDecisionReason": reason}
            blocked = True
        elif action == 'block':
            payload = {"decision": "block", "reason": reason}
            blocked = True
        elif action == 'approve':
            payload = {"decision": "approve"}
        else:
            payload = {"permissionDecision": "allow"}

        if context:
            payload["additionalContext"] = context

        if event:
            payload["hookSpecificOutput"] = {"hookEventName": event, **payload}

        return DecisionResponse(payload=payload, blocked=blocked)

    def _build_simple_response(self, rule: SimpleRule, base_context: Dict[str, Any], matched_value: str) -> DecisionResponse:
        """簡化的回應建構器 - 直接使用 rule 屬性"""
        hashed = sha1(matched_value.encode("utf-8")).hexdigest()[:12]
        context = {**base_context, "rule": rule.action, "pattern": rule.pattern.pattern, "matchDigest": hashed}
        
        if rule.action == "deny":
            return self.deny(rule.reason, event="PreToolUse", additional_context=context)
        elif rule.action == "ask":
            return self.ask(rule.reason, event="PreToolUse", additional_context=context)
        else:
            return self.allow(event="PreToolUse", additional_context=context)

    # -- Extraction utilities --------------------------------------------
    def _extract_command(self, tool_input: Optional[Dict[str, Any]]) -> str:
        if not isinstance(tool_input, dict):
            return ""
        chunks: List[str] = []
        for key in ("command", "commands", "input", "prompt", "args"):
            value = tool_input.get(key)
            if isinstance(value, str):
                chunks.append(value)
            elif isinstance(value, list):
                chunks.extend(str(item) for item in value if isinstance(item, (str, int, float)))
        return " \n".join(chunks).strip()

    def _extract_paths(self, tool_input: Optional[Dict[str, Any]]) -> List[str]:
        if not isinstance(tool_input, dict):
            return []
        paths: List[str] = []
        for key, value in tool_input.items():
            lowered = key.lower()
            if any(s in lowered for s in ("path", "file", "target")):
                if isinstance(value, str):
                    paths.append(value)
                elif isinstance(value, (list, tuple, set)):
                    paths.extend(str(item) for item in value if isinstance(item, (str, Path)))
        return paths

    def _match_path(self, pattern: re.Pattern[str], paths: Iterable[str]) -> Optional[str]:
        for path in paths:
            if pattern.search(str(path)):
                return str(path)
        return None

    def _has_error(self, result: Dict[str, Any]) -> bool:
        for key in self.policy.get("post_tool_use", {}).get("error_keys", []):
            if key in result and result[key]:
                return True
        status = result.get("status")
        return isinstance(status, str) and status.lower() in {"error", "failed", "failure"}

    def _extract_exit_code(self, result: Dict[str, Any]) -> Optional[int]:
        exit_code = result.get("exitCode")
        if isinstance(exit_code, int):
            return exit_code
        try:
            if isinstance(exit_code, str):
                return int(exit_code)
        except ValueError:
            return None
        return None

    def _is_loop_detected(self, transcript: Dict[str, Any]) -> bool:
        if transcript.get("loop_detected") or transcript.get("loopDetected"):
            return True
        annotations = transcript.get("annotations")
        if isinstance(annotations, dict) and annotations.get("loopDetected"):
            return True
        summary = transcript.get("summary")
        if isinstance(summary, str) and "loop" in summary.lower():
            return True
        return False

    # -- Policy loading ---------------------------------------------------
    def _default_policy_path(self) -> Path:
        here = Path(__file__).resolve()
        return here.parent / "decision_policy.json"

    def _load_simple_policy(self) -> Dict[str, Any]:
        """Simple policy loading with ConfigManager integration."""
        user_policy = self.config_manager.get('decision_policy', {})
        # 簡單字典合併，避免深度遞歸
        result = deepcopy(_DEFAULT_POLICY)
        for section, rules in user_policy.items():
            if section in result and isinstance(rules, dict):
                result[section].update(rules)
            else:
                result[section] = rules
        return result

    # _merge_policy 移除 - 使用簡單字典更新替代遞歸合併

    def _compile_rules(self, rules_config: List[Dict]) -> List[SimpleRule]:
        """簡化的規則編譯 - 直接處理模式，無需複雜標籤解析"""
        compiled = []
        for rule in rules_config:
            pattern_str = rule.get('pattern')
            if not pattern_str:
                continue
                
            try:
                compiled.append(SimpleRule(
                    type=rule.get('type', 'command'),
                    action=rule.get('action', 'allow'),
                    pattern=re.compile(pattern_str, re.IGNORECASE),
                    reason=rule.get('reason', '無提供原因'),
                    severity=rule.get('severity', 'medium')
                ))
            except re.error:
                # 忽略無效的正則表達式
                continue
        return compiled
