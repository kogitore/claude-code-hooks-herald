# ADR-002: Decision API Simplification Refactoring Guide

**Status**: Proposed
**Date**: 2025-09-24
**Context**: Phase 2 Herald System Optimization - Decision API Complexity Reduction

## Background

The current `decision_api.py` has grown to 570 lines with excessive abstraction layers:
- Over-engineered TagLibrary and TagMatcher systems
- Complex policy merging logic with deep recursion
- Multiple wrapper methods with similar functionality
- Redundant abstraction that obscures core decision logic

## Goals

1. **Reduce complexity**: From 570 lines to ~300 lines
2. **Eliminate over-abstraction**: Remove TagLibrary/TagMatcher complexity
3. **Simplify policy management**: Streamline ConfigManager integration
4. **Maintain functionality**: Preserve all existing decision capabilities
5. **Improve testability**: Clear separation of concerns

## Simplification Strategy

### Phase 1: Core Logic Simplification (Priority: HIGH)

#### 1.1 Remove Over-Abstraction
```python
# REMOVE: Complex TagLibrary system (lines 88-123)
_TAG_LIBRARY: Dict[str, TagDefinition] = { ... }

# REMOVE: TagMatcher class (lines 125-160)
class TagMatcher: ...

# REPLACE WITH: Simple inline rule matching
```

#### 1.2 Simplify Rule Compilation
```python
# CURRENT: Complex _compile_pre_rules with tag resolution (lines 526-570)
def _compile_pre_rules(self, policy: Dict[str, Any]) -> List[_CompiledRule]:
    # 44 lines of complex logic

# SIMPLIFIED TARGET:
def _compile_rules(self, rules_config: List[Dict]) -> List[SimpleRule]:
    # 15 lines of direct compilation
    compiled = []
    for rule in rules_config:
        if rule.get('pattern'):
            compiled.append(SimpleRule(
                type=rule.get('type', 'command'),
                action=rule.get('action', 'allow'),
                pattern=re.compile(rule['pattern'], re.IGNORECASE),
                reason=rule.get('reason', 'No reason provided'),
                severity=rule.get('severity', 'medium')
            ))
    return compiled
```

#### 1.3 Consolidate Response Builders
```python
# CURRENT: Multiple similar wrapper methods (lines 243-349)
def allow(...) -> DecisionResponse: ...
def deny(...) -> DecisionResponse: ...
def ask(...) -> DecisionResponse: ...
def block(...) -> DecisionResponse: ...
def block_stop(...) -> DecisionResponse: ...
def allow_stop(...) -> DecisionResponse: ...

# SIMPLIFIED TARGET: Single response builder with action parameter
def _build_response(self, action: str, reason: str = None, **kwargs) -> DecisionResponse:
    # Unified response building logic
```

### Phase 2: ConfigManager Integration (Priority: MEDIUM)

#### 2.1 Simplify Policy Loading
```python
# CURRENT: Complex _load_policy and _merge_policy (lines 495-525)
def _load_policy(self) -> Dict[str, Any]: ...
def _merge_policy(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]: ...

# SIMPLIFIED TARGET:
def __init__(self, config_manager: ConfigManager = None):
    self.config_manager = config_manager or ConfigManager.get_instance()
    self.policy = self._load_simple_policy()

def _load_simple_policy(self) -> Dict[str, Any]:
    # Direct policy loading with fallback
    user_policy = self.config_manager.get('decision_policy', {})
    return {**DEFAULT_POLICY, **user_policy}  # Simple merge
```

### Phase 3: Data Structure Optimization (Priority: LOW)

#### 3.1 Simplify Data Classes
```python
# CURRENT: Multiple complex dataclasses
@dataclass(frozen=True)
class TagDefinition: ...

@dataclass
class _CompiledRule: ...

# SIMPLIFIED TARGET: Single rule class
@dataclass
class SimpleRule:
    type: str
    action: str
    pattern: re.Pattern
    reason: str
    severity: str = 'medium'
```

## Implementation Steps

### Step 1: Backup and Branch
```bash
git checkout -b refactor/decision-api-simplification
cp utils/decision_api.py utils/decision_api.py.backup
```

### Step 2: Replace TagLibrary System
1. Remove `_TAG_LIBRARY` constant (lines 88-123)
2. Remove `TagMatcher` class (lines 125-160)
3. Update `_compile_pre_rules` to use direct pattern matching

### Step 3: Simplify Rule Compilation
1. Replace `_CompiledRule` with `SimpleRule`
2. Simplify `_compile_pre_rules` to `_compile_rules`
3. Remove tag resolution complexity

### Step 4: Consolidate Response Methods
1. Create single `_build_response` method
2. Update all `allow/deny/ask/block` methods to use unified builder
3. Preserve public API compatibility

### Step 5: Streamline Policy Management
1. Simplify `_load_policy` method
2. Replace recursive `_merge_policy` with simple dict merge
3. Integrate with existing ConfigManager instance

### Step 6: Update Tests
```bash
# Update existing tests to match simplified API
uv run python tests/test_integration_verification.py
```

## Expected Outcomes

### Complexity Reduction
- **Lines of code**: 570 → ~300 lines (-47%)
- **Cyclomatic complexity**: High → Medium
- **Abstraction layers**: 4 → 2 layers

### Performance Improvements
- **Rule compilation**: Faster without tag resolution
- **Memory usage**: Reduced due to fewer objects
- **Initialization time**: Faster policy loading

### Maintainability Gains
- **Easier debugging**: Clearer execution paths
- **Simpler testing**: Fewer edge cases
- **Better documentation**: Less complex behavior to document

## Risk Mitigation

### Functional Preservation
- All public methods maintain same signatures
- Decision logic outcomes remain identical
- ConfigManager integration preserved

### Testing Strategy
- Run full test suite before/after changes
- Verify integration tests pass
- Compare decision outputs on sample inputs

### Rollback Plan
- Backup file: `decision_api.py.backup`
- Feature branch allows easy revert
- ConfigManager integration remains optional

## Success Criteria

- [ ] Code complexity reduced by 40%+
- [ ] All existing tests pass
- [ ] Public API compatibility maintained
- [ ] ConfigManager integration working
- [ ] Performance improved or maintained
- [ ] No functional regressions

## Implementation Timeline

- **Day 1**: Steps 1-3 (Core simplification)
- **Day 2**: Steps 4-5 (API consolidation)
- **Day 3**: Step 6 (Testing and validation)

---

*Generated for Herald System Phase 2 Optimization - 2025-09-24*