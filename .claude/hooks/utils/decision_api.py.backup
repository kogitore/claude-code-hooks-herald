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


@dataclass(frozen=True)
class TagDefinition:
    rule_type: str
    pattern: str
    severity: Optional[str] = None
    description: Optional[str] = None


_TAG_LIBRARY: Dict[str, TagDefinition] = {
    "system:dangerous": TagDefinition(
        rule_type="command",
        pattern=r"(?:^|[;&|]\s*)(?:rm\s+-rf\s+(?:/|~|\$HOME)|shutdown|halt|reboot)\b",
        severity="critical",
        description="Potentially destructive system commands",
    ),
    "package:install": TagDefinition(
        rule_type="command",
        pattern=r"(?:^|[;&|]\s*)(?:npm|pnpm|yarn|pip|poetry|uvx?)\s+(?:install|add|update)\b",
        severity="medium",
        description="Package installation or upgrade",
    ),
    "package:remove": TagDefinition(
        rule_type="command",
        pattern=r"(?:^|[;&|]\s*)(?:npm|pnpm|yarn|pip|poetry|uvx?)\s+(?:uninstall|remove)\b",
        severity="medium",
    ),
    "git:destructive": TagDefinition(
        rule_type="command",
        pattern=r"(?:^|[;&|]\s*)git\s+(?:reset\s+--hard|clean\s+-fd|checkout\s+--|restore\s+--source)\b",
        severity="high",
        description="Git commands that drop local changes",
    ),
    "secrets:file": TagDefinition(
        rule_type="path",
        pattern=r"\.env(?:\.|$)|secret|credentials|id_(?:rsa|ed25519)|\.pem$",
        severity="high",
    ),
    "dependency:lock": TagDefinition(
        rule_type="path",
        pattern=r"(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|requirements(?:\.(txt|in))?)$",
        severity="medium",
    ),
}


class TagMatcher:
    def __init__(self, registry: Optional[Dict[str, TagDefinition]] = None) -> None:
        self.registry = registry or _TAG_LIBRARY

    def build(
        self, tags: List[str], explicit_type: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[str], List[str]]:
        patterns: List[str] = []
        resolved_tags: List[str] = []
        severities: List[str] = []
        rule_type = explicit_type

        for tag in tags:
            definition = self.registry.get(tag)
            if not definition:
                continue
            resolved_tags.append(tag)
            if rule_type is None:
                rule_type = definition.rule_type
            if rule_type == definition.rule_type:
                patterns.append(definition.pattern)
            if definition.severity:
                severities.append(definition.severity)

        if not patterns:
            return explicit_type, None, None, resolved_tags

        combined_pattern = "|".join(f"(?:{p})" for p in patterns)
        severity = self._max_severity(severities)
        return rule_type or "command", combined_pattern, severity, resolved_tags

    def _max_severity(self, severities: List[str]) -> Optional[str]:
        if not severities:
            return None
        return max(severities, key=lambda s: _SEVERITY_ORDER.get(s, -1))


@dataclass
class DecisionResponse:
    payload: Dict[str, Any]
    blocked: bool = False
    severity: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.payload


@dataclass
class _CompiledRule:
    rule_type: str
    action: str
    pattern: re.Pattern[str]
    reason: str
    tags: List[str] = field(default_factory=list)
    severity: Optional[str] = None


class DecisionAPI:
    def __init__(self, policy_path: Optional[Path] = None) -> None:
        self.policy_path = policy_path or self._default_policy_path()
        
        # Initialize ConfigManager with the directory containing decision policy files
        config_dir = self.policy_path.parent
        self._config_manager = ConfigManager.get_instance([str(config_dir)])
        
        self.policy = self._load_policy()
        self._tag_matcher = TagMatcher()
        self._pre_rules: List[_CompiledRule] = self._compile_pre_rules(self.policy)

    # -- Public decision helpers -----------------------------------------
    def pre_tool_use_decision(self, tool_name: str, tool_input: Optional[Dict[str, Any]]) -> DecisionResponse:
        command_blob = self._extract_command(tool_input)
        paths = self._extract_paths(tool_input)
        context_base = {"tool": tool_name}

        for rule in self._pre_rules:
            if rule.rule_type == "command" and command_blob:
                if rule.pattern.search(command_blob):
                    return self._build_pre_response(rule, context_base, command_blob)
            elif rule.rule_type == "path" and paths:
                matched_path = self._match_path(rule.pattern, paths)
                if matched_path:
                    return self._build_pre_response(rule, context_base, matched_path)

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
        return self._wrap_permission(
            "allow",
            event=event,
            additional_context=additional_context,
            severity=severity,
            tags=tags,
        )

    def deny(
        self,
        reason: str,
        *,
        event: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        body = {"permissionDecisionReason": reason}
        return self._wrap_permission(
            "deny",
            body=body,
            event=event,
            additional_context=additional_context,
            blocked=True,
            severity=severity,
            tags=tags,
        )

    def ask(
        self,
        reason: str,
        *,
        event: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        body = {"permissionDecisionReason": reason}
        return self._wrap_permission(
            "ask",
            body=body,
            event=event,
            additional_context=additional_context,
            blocked=True,
            severity=severity,
            tags=tags,
        )

    def block(
        self,
        reason: str,
        *,
        event: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        payload = {"decision": "block", "reason": reason}
        return self._wrap(
            event=event,
            payload=payload,
            additional_context=additional_context,
            blocked=True,
            severity=severity,
            tags=tags,
        )

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
        payload = {"decision": "approve"}
        return self._wrap(
            event="Stop",
            payload=payload,
            additional_context=additional_context,
            blocked=False,
            severity=severity,
            tags=tags,
        )

    # -- Internal helpers -------------------------------------------------
    def _wrap_permission(
        self,
        decision: str,
        *,
        body: Optional[Dict[str, Any]] = None,
        event: Optional[str],
        additional_context: Optional[Dict[str, Any]],
        blocked: bool = False,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        payload = {"permissionDecision": decision}
        if body:
            payload.update(body)
        return self._wrap(
            event=event,
            payload=payload,
            additional_context=additional_context,
            blocked=blocked,
            severity=severity,
            tags=tags,
        )

    def _wrap(
        self,
        *,
        event: Optional[str],
        payload: Dict[str, Any],
        additional_context: Optional[Dict[str, Any]],
        blocked: bool,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> DecisionResponse:
        context_copy = dict(additional_context or {})
        if tags:
            context_copy.setdefault("tags", tags)
        if severity:
            context_copy.setdefault("severity", severity)
        if context_copy:
            payload = {**payload, "additionalContext": context_copy}

        if event:
            hook_output = {"hookEventName": event, **payload}
            payload = {**payload, "hookSpecificOutput": hook_output}

        return DecisionResponse(payload=payload, blocked=blocked, severity=severity, tags=tags or [])

    def _build_pre_response(self, rule: _CompiledRule, base_context: Dict[str, Any], matched_value: str) -> DecisionResponse:
        hashed = sha1(matched_value.encode("utf-8")).hexdigest()[:12]
        context = {**base_context, "rule": rule.action, "pattern": rule.pattern.pattern, "matchDigest": hashed}
        if rule.tags:
            context.setdefault("tags", rule.tags)
        if rule.severity:
            context.setdefault("severity", rule.severity)
        if rule.action == "deny":
            return self.deny(
                rule.reason,
                event="PreToolUse",
                additional_context=context,
                severity=rule.severity,
                tags=rule.tags,
            )
        if rule.action == "ask":
            return self.ask(
                rule.reason,
                event="PreToolUse",
                additional_context=context,
                severity=rule.severity,
                tags=rule.tags,
            )
        return self.allow(
            event="PreToolUse",
            additional_context=context,
            severity=rule.severity,
            tags=rule.tags,
        )

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

    def _load_policy(self) -> Dict[str, Any]:
        """Load policy using ConfigManager with fallback to defaults."""
        policy_filename = self.policy_path.name
        
        try:
            # Use ConfigManager to load the policy file
            user_policy = self._config_manager.get_config(policy_filename)
            if user_policy:  # ConfigManager returns empty dict if file not found
                return self._merge_policy(deepcopy(_DEFAULT_POLICY), user_policy)
        except Exception:
            # ConfigManager handles errors gracefully, but we add extra safety
            pass
        
        return deepcopy(_DEFAULT_POLICY)

    def _merge_policy(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in overrides.items():
            if key not in base:
                base[key] = value
                continue
            if isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._merge_policy(dict(base[key]), value)
            elif isinstance(base[key], list) and isinstance(value, list):
                if key == "rules":
                    base[key] = base[key] + value
                else:
                    base[key] = value
            else:
                base[key] = value
        return base

    def _compile_pre_rules(self, policy: Dict[str, Any]) -> List[_CompiledRule]:
        rules_cfg = policy.get("pre_tool_use", {}).get("rules", [])
        compiled: List[_CompiledRule] = []
        for item in rules_cfg:
            rule_type = item.get("type")
            rule_type = str(rule_type) if isinstance(rule_type, str) and rule_type else None
            action = str(item.get("action", "allow"))
            pattern_str = item.get("pattern")
            pattern_str = str(pattern_str) if isinstance(pattern_str, str) and pattern_str else None
            reason = str(item.get("reason", "未提供原因"))
            raw_tags = item.get("tags") or []
            tags = [str(tag) for tag in raw_tags if isinstance(tag, str)]
            severity = str(item.get("severity")) if item.get("severity") else None

            if tags:
                resolved_type, tag_pattern, tag_severity, resolved_tags = self._tag_matcher.build(tags, rule_type)
                if resolved_tags:
                    tags = resolved_tags
                if not pattern_str and tag_pattern:
                    pattern_str = tag_pattern
                if severity is None and tag_severity:
                    severity = tag_severity
                if rule_type is None and resolved_type:
                    rule_type = resolved_type

            if not pattern_str:
                continue

            try:
                compiled_pattern = re.compile(pattern_str, re.IGNORECASE)
            except re.error:
                continue

            compiled.append(
                _CompiledRule(
                    rule_type=rule_type or "command",
                    action=action,
                    pattern=compiled_pattern,
                    reason=reason,
                    tags=list(dict.fromkeys(tags)),
                    severity=severity,
                )
            )
        return compiled
