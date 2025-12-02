#!/usr/bin/env python3
"""Skill rules loader - loads skill triggers from JSON configuration.

Based on skill-activation pattern from claude-code-infrastructure-showcase.
Supports both keyword matching and regex intent patterns.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger("hooks.skill_rules")
if not _log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    _log.addHandler(_handler)
    _log.setLevel(logging.WARNING)

# Default path to skill-rules.json
SKILL_RULES_PATH = Path(__file__).resolve().parents[2] / "skills" / "skill-rules.json"


@dataclass
class SkillMatch:
    """Represents a matched skill with metadata."""

    name: str
    match_type: str  # "keyword" or "intent"
    priority: str  # "critical", "high", "medium", "low"
    enforcement: str  # "suggest", "block", "warn"
    description: str = ""


@dataclass
class SkillRulesConfig:
    """Parsed skill rules configuration."""

    version: str = "1.0"
    skills: dict[str, dict[str, object]] = field(default_factory=dict)
    _compiled_patterns: dict[str, list[re.Pattern[str]]] = field(default_factory=dict, repr=False)

    def get_keywords(self, skill_name: str) -> tuple[str, ...]:
        """Get keywords for a skill."""
        skill = self.skills.get(skill_name, {})
        triggers = skill.get("promptTriggers", {})
        if isinstance(triggers, dict):
            keywords = triggers.get("keywords", [])
            if isinstance(keywords, list):
                return tuple(str(k).lower() for k in keywords)
        return ()

    def get_intent_patterns(self, skill_name: str) -> list[re.Pattern[str]]:
        """Get compiled intent patterns for a skill."""
        if skill_name in self._compiled_patterns:
            return self._compiled_patterns[skill_name]

        skill = self.skills.get(skill_name, {})
        triggers = skill.get("promptTriggers", {})
        patterns: list[re.Pattern[str]] = []

        if isinstance(triggers, dict):
            raw_patterns = triggers.get("intentPatterns", [])
            if isinstance(raw_patterns, list):
                for p in raw_patterns:
                    try:
                        patterns.append(re.compile(str(p), re.IGNORECASE))
                    except re.error as e:
                        _log.warning("Invalid regex pattern '%s' for skill '%s': %s", p, skill_name, e)

        self._compiled_patterns[skill_name] = patterns
        return patterns

    def get_priority(self, skill_name: str) -> str:
        """Get priority level for a skill."""
        skill = self.skills.get(skill_name, {})
        return str(skill.get("priority", "medium"))

    def get_enforcement(self, skill_name: str) -> str:
        """Get enforcement type for a skill."""
        skill = self.skills.get(skill_name, {})
        return str(skill.get("enforcement", "suggest"))

    def get_description(self, skill_name: str) -> str:
        """Get description for a skill."""
        skill = self.skills.get(skill_name, {})
        return str(skill.get("description", ""))


# Singleton cache
_rules_cache: SkillRulesConfig | None = None
_rules_mtime: float = 0.0


def load_skill_rules(force_reload: bool = False) -> SkillRulesConfig:
    """Load skill rules from JSON file with caching.

    Args:
        force_reload: Force reload even if cached.

    Returns:
        SkillRulesConfig instance.
    """
    global _rules_cache, _rules_mtime

    if not SKILL_RULES_PATH.exists():
        _log.debug("skill-rules.json not found at %s, using empty config", SKILL_RULES_PATH)
        return SkillRulesConfig()

    try:
        current_mtime = SKILL_RULES_PATH.stat().st_mtime
    except OSError:
        current_mtime = 0.0

    # Return cached if not modified
    if not force_reload and _rules_cache is not None and current_mtime == _rules_mtime:
        return _rules_cache

    try:
        with SKILL_RULES_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)

        config = SkillRulesConfig(
            version=data.get("version", "1.0"),
            skills=data.get("skills", {}),
        )
        _rules_cache = config
        _rules_mtime = current_mtime
        _log.debug("Loaded skill rules v%s with %d skills", config.version, len(config.skills))
        return config

    except (json.JSONDecodeError, OSError) as e:
        _log.warning("Failed to load skill-rules.json: %s", e)
        return SkillRulesConfig()


def match_skills(prompt: str, config: SkillRulesConfig | None = None) -> list[SkillMatch]:
    """Match prompt against skill rules.

    Args:
        prompt: User prompt to match.
        config: Optional config (loads from file if not provided).

    Returns:
        List of matched skills sorted by priority.
    """
    if config is None:
        config = load_skill_rules()

    if not prompt.strip():
        return []

    lowered = prompt.lower()
    matches: list[SkillMatch] = []

    for skill_name in config.skills:
        # Keyword matching
        keywords = config.get_keywords(skill_name)
        keyword_match = any(kw in lowered for kw in keywords)

        if keyword_match:
            matches.append(SkillMatch(
                name=skill_name,
                match_type="keyword",
                priority=config.get_priority(skill_name),
                enforcement=config.get_enforcement(skill_name),
                description=config.get_description(skill_name),
            ))
            continue  # Skip intent matching if keyword matched

        # Intent pattern matching
        patterns = config.get_intent_patterns(skill_name)
        intent_match = any(p.search(prompt) for p in patterns)

        if intent_match:
            matches.append(SkillMatch(
                name=skill_name,
                match_type="intent",
                priority=config.get_priority(skill_name),
                enforcement=config.get_enforcement(skill_name),
                description=config.get_description(skill_name),
            ))

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    matches.sort(key=lambda m: priority_order.get(m.priority, 99))

    return matches


def suggest_skills_from_rules(prompt: str) -> tuple[str, ...]:
    """Suggest skills based on prompt content using JSON rules.

    This is a drop-in replacement for the hardcoded SKILL_TRIGGERS dict.

    Args:
        prompt: User prompt to analyze.

    Returns:
        Tuple of skill names that match.
    """
    matches = match_skills(prompt)
    return tuple(m.name for m in matches)


# Fallback hardcoded triggers (used if skill-rules.json doesn't exist)
FALLBACK_TRIGGERS: dict[str, tuple[str, ...]] = {
    "test": ("pytest", "unittest", "test coverage", "run tests", "測試"),
    "refactor": ("refactor", "clean up", "reorganize", "重構"),
    "debug": ("error", "bug", "fix", "broken", "錯誤", "修復"),
    "review": ("review", "code review", "審查"),
    "docs": ("document", "docstring", "readme", "文件"),
}


def suggest_skills(prompt: str) -> tuple[str, ...]:
    """Suggest skills with fallback to hardcoded triggers.

    Uses JSON rules if available, falls back to hardcoded dict otherwise.

    Args:
        prompt: User prompt to analyze.

    Returns:
        Tuple of skill names that match.
    """
    config = load_skill_rules()

    # If we have skills defined in JSON, use them
    if config.skills:
        return suggest_skills_from_rules(prompt)

    # Fallback to hardcoded triggers
    if not prompt:
        return ()

    suggestions: list[str] = []
    lowered = prompt.lower()

    for skill, keywords in FALLBACK_TRIGGERS.items():
        if any(kw in lowered for kw in keywords):
            suggestions.append(skill)

    return tuple(dict.fromkeys(suggestions))
