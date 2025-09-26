---
id: 0003
status: accepted
date: 2025-09-18
related: [0001, 0002]
---

> **[中文版本](./0003-decision-policy-template_zh-TW.md)**

# Decision: Advanced Decision Policy Templates

## Context
- Herald now routes all official events (Notification, Stop, SubagentStop, Pre/PostToolUse, Session) through a single dispatcher.
- The built-in policy blocks destructive commands (`rm -rf /`) and obvious credential edits, but teams frequently need extra rules (package managers, infrastructure scripts, etc.).
- Manual edits to `decision_policy.json` are error-prone because JSON lacks comments and rule ordering matters.

## Options Considered
1. **Document-only guidance** — describe patterns in README; users craft JSON from scratch.
2. **Provide commented JSON** — supply an example file beside the active policy that users can copy.
3. **Generate policy via CLI** — build a wizard that writes JSON interactively.

## Decision
Ship a rich example file (`decision_policy.example.json`) and accompanying documentation that explains how to copy, trim, and extend rules. Keep the example close to the runtime location (`.claude/hooks/utils/`) so editors find it easily, and pair it with bilingual guidance in README.

## Consequences
- **Positive**: Faster onboarding; users can paste common patterns (deny git reset, ask for sudo installs, etc.) without memorising regex syntax. Aligns README/README_zh-TW sections with concrete examples.
- **Trade-offs**: Need to maintain the example when defaults change; no inline comments (JSON format). Mitigated by `metadata.notes` in the template.

## Implementation Notes
- Template located at `.claude/hooks/utils/decision_policy.example.json` with:
  - Sample deny/ask rules for commands and file paths.
  - Optional metadata, default action, and post-tool/stop/session hints.
- README (English/Chinese) link to the template and summarise editing steps.
- Tests (`test_decision_api.py::test_custom_policy_extends_rules`) assert that custom rules merge on top of defaults.

## References
- `.claude/hooks/utils/decision_api.py`
- `.claude/hooks/utils/decision_policy.json`
- `.claude/hooks/tests/test_decision_api.py`
- `README.md`, `README_zh-TW.md`
