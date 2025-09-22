---
id: 0004
status: accepted
date: 2025-09-18
related: [0003]
---

> **[中文版本](./0004-decision-tags_zh-TW.md)**

# Decision: Tag-driven Decision Policy

## Context
- Regex-only policies are hard to maintain: teams repeatedly copy complicated patterns for package installs, git resets, and credential edits.
- The new `decision_policy.example.json` already exposes `tags`, but the runtime ignored them; users still had to supply raw regex.
- We want semantic tagging plus severity levels so policies are readable and auditable.

## Decision
Augment `DecisionAPI` with a built-in tag library and severity ranking. A rule can now specify `"tags": ["package:install"]` (and optionally a custom regex). Each tag resolves to a pre-defined pattern, default severity, and rule type (command vs path). Severity propagates into the decision response and logs.

## Consequences
- **Positive**: Lower entry barrier; most teams can express common safety nets with a handful of tags. Severity metadata enables dashboards or future middleware to prioritise incidents.
- **Neutral**: Regex remains supported for advanced cases and coexists with tags.
- **Negative**: Tag library must be versioned carefully; adding/removing tags may surprise users if semantics change.

## Implementation Notes
- Introduced `TagMatcher` and `_TAG_LIBRARY` in `.claude/hooks/utils/decision_api.py` with seed tags (`system:dangerous`, `package:install`, `git:destructive`, `secrets:file`, `dependency:lock`).
- `_CompiledRule` now stores `tags` and `severity`; `_build_pre_response` includes them in `additionalContext` and `DecisionResponse` fields.
- Updated default policy, user policy, template, README, and README_zh-TW to describe available tags and severity levels.
- Added unit tests (`test_decision_api.py::test_tag_rule_matches`) ensuring tag matching and severity propagation, plus template ADR 0003 cross-links.

## References
- `.claude/hooks/utils/decision_api.py`
- `.claude/hooks/utils/decision_policy.json`
- `.claude/hooks/utils/decision_policy.example.json`
- `.claude/hooks/tests/test_decision_api.py`
- `README.md`, `README_zh-TW.md`
