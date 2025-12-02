#!/usr/bin/env python3
"""Tests for Skill Auto-Activation pattern in UserPromptSubmit hook."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_DIR = REPO_ROOT / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from herald.handlers.user_prompt_submit import _suggest_skills
from herald.utils.skill_rules import load_skill_rules, FALLBACK_TRIGGERS


class TestSkillSuggestions(unittest.TestCase):
    """Tests for skill auto-activation functionality."""

    def test_suggest_skills_returns_empty_for_empty_prompt(self) -> None:
        """Empty prompts should return no skill suggestions."""
        result = _suggest_skills("")
        self.assertEqual(result, ())

    def test_suggest_skills_detects_test_keywords(self) -> None:
        """Test-related keywords should suggest 'test' skill."""
        prompts = [
            "run pytest on the module",
            "check test coverage",
            "help me run tests",
            "執行測試",  # Chinese: run tests
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                result = _suggest_skills(prompt)
                self.assertIn("test", result, f"Expected 'test' in suggestions for: {prompt}")

    def test_suggest_skills_detects_debug_keywords(self) -> None:
        """Debug-related keywords should suggest 'debug' skill."""
        prompts = [
            "fix the bug in login",
            "there's an error when saving",
            "something is broken",
            "修復這個錯誤",  # Chinese: fix this error
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                result = _suggest_skills(prompt)
                self.assertIn("debug", result, f"Expected 'debug' in suggestions for: {prompt}")

    def test_suggest_skills_detects_refactor_keywords(self) -> None:
        """Refactor-related keywords should suggest 'refactor' skill."""
        prompts = [
            "refactor this function",
            "clean up the code",
            "reorganize the module structure",
            "重構這段程式碼",  # Chinese: refactor this code
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                result = _suggest_skills(prompt)
                self.assertIn("refactor", result, f"Expected 'refactor' in suggestions for: {prompt}")

    def test_suggest_skills_detects_review_keywords(self) -> None:
        """Review-related keywords should suggest 'review' skill."""
        prompts = [
            "review this code",
            "do a code review",
            "審查這個 PR",  # Chinese: review this PR
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                result = _suggest_skills(prompt)
                self.assertIn("review", result, f"Expected 'review' in suggestions for: {prompt}")

    def test_suggest_skills_detects_docs_keywords(self) -> None:
        """Documentation-related keywords should suggest 'docs' skill."""
        prompts = [
            "add documentation for the API",
            "write docstrings for functions",
            "update the readme file",
            "寫文件",  # Chinese: write documentation
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                result = _suggest_skills(prompt)
                self.assertIn("docs", result, f"Expected 'docs' in suggestions for: {prompt}")

    def test_suggest_skills_detects_multiple_skills(self) -> None:
        """Prompts with multiple keywords should suggest multiple skills."""
        prompt = "fix the bug and run tests"
        result = _suggest_skills(prompt)
        self.assertIn("debug", result)
        self.assertIn("test", result)

    def test_suggest_skills_no_match_returns_empty(self) -> None:
        """Prompts with no matching keywords should return empty tuple."""
        prompt = "print hello world"
        result = _suggest_skills(prompt)
        self.assertEqual(result, ())

    def test_suggest_skills_case_insensitive(self) -> None:
        """Skill detection should be case-insensitive."""
        prompts = ["RUN PYTEST", "Run Tests", "REFACTOR this"]
        expected = ["test", "test", "refactor"]
        for prompt, expected_skill in zip(prompts, expected):
            with self.subTest(prompt=prompt):
                result = _suggest_skills(prompt)
                self.assertIn(expected_skill, result)

    def test_skill_rules_structure(self) -> None:
        """Verify skill-rules.json or fallback has expected structure."""
        config = load_skill_rules()

        # Check if JSON rules are loaded
        if config.skills:
            # JSON-based rules
            expected_base_skills = {"test", "refactor", "debug", "review", "docs"}
            loaded_skills = set(config.skills.keys())
            # Should at least have the base skills
            self.assertTrue(
                expected_base_skills.issubset(loaded_skills),
                f"Expected at least {expected_base_skills}, got {loaded_skills}"
            )
            for skill_name in config.skills:
                keywords = config.get_keywords(skill_name)
                self.assertIsInstance(keywords, tuple)
                self.assertTrue(len(keywords) > 0, f"Skill '{skill_name}' should have at least one keyword")
        else:
            # Fallback triggers
            expected_skills = {"test", "refactor", "debug", "review", "docs"}
            self.assertEqual(set(FALLBACK_TRIGGERS.keys()), expected_skills)
            for skill, keywords in FALLBACK_TRIGGERS.items():
                self.assertIsInstance(keywords, tuple)
                self.assertTrue(len(keywords) > 0, f"Skill '{skill}' should have at least one keyword")


class TestSkillSuggestionsIntegration(unittest.TestCase):
    """Integration tests for skill suggestions in handler output."""

    def _dispatch(self, payload: dict) -> object:
        """Dispatch a user prompt submit event."""
        disp = build_default_dispatcher()  # noqa: F821 - injected by conftest
        return disp.dispatch("UserPromptSubmit", payload=payload)

    def test_handler_includes_skill_suggestions_in_context(self) -> None:
        """Handler should include suggestedSkills in additionalContext."""
        payload = {"prompt": "run pytest on the project"}
        report = self._dispatch(payload)

        hso = report.response.get("hookSpecificOutput", {})
        ctx_str = hso.get("additionalContext", "{}")
        context = json.loads(ctx_str) if isinstance(ctx_str, str) else ctx_str

        self.assertIn("suggestedSkills", context)
        self.assertIn("test", context["suggestedSkills"])

    def test_handler_omits_skill_suggestions_when_empty(self) -> None:
        """Handler should not include suggestedSkills when no matches."""
        payload = {"prompt": "print hello world"}
        report = self._dispatch(payload)

        hso = report.response.get("hookSpecificOutput", {})
        ctx_str = hso.get("additionalContext", "{}")
        context = json.loads(ctx_str) if isinstance(ctx_str, str) else ctx_str

        # suggestedSkills should not be present or should be empty
        skills = context.get("suggestedSkills", [])
        self.assertEqual(skills, [])


if __name__ == "__main__":
    unittest.main()
