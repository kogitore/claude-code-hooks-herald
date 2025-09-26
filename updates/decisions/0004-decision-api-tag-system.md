---
id: 0004
status: proposed
date: 2025-09-18
related: [0003]
---

# Decision: Tag-Based Decision API with Severity Levels

## Context
The current DecisionAPI requires users to write regex patterns manually, which is error-prone and not user-friendly. While `decision_policy.example.json` includes `tags` fields, the DecisionAPI doesn't utilize them. Teams frequently need the same patterns (package managers, git operations, file permissions) but struggle with regex syntax.

## Problem
1. **High barrier to entry** - Users must understand regex to customize policies
2. **Pattern duplication** - Common scenarios (npm install, git reset, secret files) require manual regex
3. **No severity system** - All violations are treated equally
4. **Maintenance burden** - Regex patterns need updates when new tools emerge

## Proposed Solution
Extend DecisionAPI with a tag-based system that abstracts common patterns into semantic tags while preserving regex flexibility for advanced users.

### Tag Categories & Built-in Patterns

```python
BUILT_IN_TAG_PATTERNS = {
    # Package Management
    "package:install": [
        r"npm\s+install",
        r"pip\s+install",
        r"poetry\s+add",
        r"yarn\s+add",
        r"uv\s+pip\s+install"
    ],
    "package:uninstall": [
        r"npm\s+(uninstall|remove)",
        r"pip\s+uninstall",
        r"poetry\s+remove"
    ],

    # Git Operations
    "git:destructive": [
        r"git\s+reset\s+--hard",
        r"git\s+clean\s+-[fd]",
        r"git\s+rebase\s+--abort"
    ],
    "git:history": [
        r"git\s+rebase\s+-i",
        r"git\s+commit\s+--amend",
        r"git\s+cherry-pick"
    ],

    # System Operations
    "system:dangerous": [
        r"rm\s+-rf\s+/",
        r"sudo\s+rm\s+-rf",
        r"chmod\s+777"
    ],
    "system:admin": [
        r"sudo\s+",
        r"doas\s+",
        r"su\s+-"
    ],

    # File Types
    "files:secrets": [
        r"\.env(\.|$)",
        r"id_(rsa|ed25519)",
        r".*\.key$",
        r".*password.*"
    ],
    "files:config": [
        r"package\.json$",
        r"pyproject\.toml$",
        r"Cargo\.toml$"
    ]
}
```

### Enhanced Rule Definition

```json
{
  "pre_tool_use": {
    "rules": [
      {
        "tags": ["system:dangerous"],
        "action": "deny",
        "severity": "critical",
        "reason": "Destructive system commands blocked"
      },
      {
        "tags": ["package:install", "system:admin"],
        "action": "ask",
        "severity": "medium",
        "reason": "Package installation with elevated privileges"
      },
      {
        "pattern": "custom\\.regex",
        "action": "deny",
        "severity": "high",
        "reason": "Custom pattern for advanced users"
      }
    ],
    "severity_thresholds": {
      "critical": "deny",
      "high": "ask",
      "medium": "ask",
      "low": "allow"
    }
  }
}
```

### API Implementation

```python
@dataclass
class _CompiledRule:
    rule_type: str
    action: str
    pattern: Optional[re.Pattern[str]]
    reason: str
    tags: List[str] = field(default_factory=list)
    severity: str = "medium"

    def matches_command(self, command: str, tag_matcher: 'TagMatcher') -> bool:
        if self.pattern and self.pattern.search(command):
            return True
        return tag_matcher.matches_any(command, self.tags)

class TagMatcher:
    def __init__(self, built_in_patterns: Dict[str, List[str]]):
        self.compiled_patterns = {
            tag: [re.compile(p, re.IGNORECASE) for p in patterns]
            for tag, patterns in built_in_patterns.items()
        }

    def matches_any(self, text: str, tags: List[str]) -> bool:
        for tag in tags:
            if tag in self.compiled_patterns:
                for pattern in self.compiled_patterns[tag]:
                    if pattern.search(text):
                        return True
        return False

class DecisionAPI:
    def __init__(self, policy_path: Optional[Path] = None):
        # ... existing init ...
        self.tag_matcher = TagMatcher(BUILT_IN_TAG_PATTERNS)

    def pre_tool_use_decision(self, tool_name: str, tool_input: Optional[Dict[str, Any]]) -> DecisionResponse:
        command_blob = self._extract_command(tool_input)

        for rule in self._pre_rules:
            if rule.matches_command(command_blob, self.tag_matcher):
                # Apply severity-based action override if configured
                final_action = self._resolve_action(rule.action, rule.severity)
                return self._build_response(rule, tool_name, command_blob, final_action)

        return self.allow(event="PreToolUse", additional_context={"tool": tool_name})
```

## Backwards Compatibility
- Existing regex-based rules continue to work unchanged
- Tags are additive - a rule can have both `pattern` and `tags`
- Built-in tag patterns can be overridden in user policy
- Severity is optional, defaults to "medium"

## Migration Path
1. **Phase 1**: Implement tag system alongside existing regex
2. **Phase 2**: Update `decision_policy.example.json` with tag examples
3. **Phase 3**: Document migration guide for regex → tags
4. **Phase 4**: Add CLI helper to suggest tags for common patterns

## Benefits
- **Lower barrier**: Users write `"tags": ["package:install"]` instead of complex regex
- **Consistency**: Standard patterns across teams and projects
- **Extensibility**: New tool patterns added to built-ins via updates
- **Flexibility**: Power users can still use custom regex when needed
- **Prioritization**: Severity levels allow fine-grained policy control

## Implementation Checklist
- [ ] Extend `_CompiledRule` with tags and severity
- [ ] Implement `TagMatcher` class
- [ ] Update `_compile_pre_rules` to handle tags
- [ ] Add severity threshold resolution
- [ ] Update tests to cover tag matching
- [ ] Update documentation and examples
- [ ] Add CLI helper for tag discovery

## References
- Current: `.claude/hooks/utils/decision_api.py`
- Template: `.claude/hooks/utils/decision_policy.example.json`
- Related: ADR-0003 (Decision Policy Templates)