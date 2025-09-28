# Decision API 簡化重構 - 實作檢查清單

## 🎯 重構目標
- 將 570 行程式碼簡化至 ~300 行 (-47%)
- 移除過度抽象化 (TagLibrary/TagMatcher)
- 簡化 ConfigManager 整合
- 保持所有現有功能完整性

## 📋 實作步驟清單

### Phase 1: 核心邏輯簡化 (高優先級)

#### ✅ Step 1: 環境準備
- [ ] `git checkout -b refactor/decision-api-simplification`
- [ ] `cp utils/decision_api.py utils/decision_api.py.backup`
- [ ] 確認測試可執行：`uv run python tests/test_integration_verification.py`

#### ✅ Step 2: 移除過度抽象化 (目標：-120 行)
**移除以下代碼段：**
- [ ] `_TAG_LIBRARY` 常數定義 (lines 88-123) - 移除 36 行
- [ ] `TagDefinition` 類別 (lines 80-86) - 移除 7 行
- [ ] `TagMatcher` 類別 (lines 125-160) - 移除 36 行
- [ ] `_tag_matcher` 實例化 (line 192)

**替換為簡單的內聯匹配邏輯**

#### ✅ Step 3: 簡化規則編譯 (目標：-30 行)
**當前代碼 (lines 526-570, 44 行):**
```python
def _compile_pre_rules(self, policy: Dict[str, Any]) -> List[_CompiledRule]:
    # 複雜的標籤解析邏輯
```

**替換為 (目標：~15 行):**
```python
@dataclass
class SimpleRule:
    type: str
    action: str
    pattern: re.Pattern
    reason: str
    severity: str = 'medium'

def _compile_rules(self, rules_config: List[Dict]) -> List[SimpleRule]:
    compiled = []
    for rule in rules_config:
        if rule.get('pattern'):
            try:
                compiled.append(SimpleRule(
                    type=rule.get('type', 'command'),
                    action=rule.get('action', 'allow'),
                    pattern=re.compile(rule['pattern'], re.IGNORECASE),
                    reason=rule.get('reason', '無提供原因'),
                    severity=rule.get('severity', 'medium')
                ))
            except re.error:
                continue
    return compiled
```

#### ✅ Step 4: 統一回應建構器 (目標：-50 行)
**當前代碼：6 個類似的方法 (lines 243-349)**
- `allow()`, `deny()`, `ask()`, `block()`, `block_stop()`, `allow_stop()`

**替換為單一建構器:**
```python
def _build_response(self, action: str, reason: str = None,
                   event: str = None, blocked: bool = False, **context) -> DecisionResponse:
    if action == 'allow':
        payload = {"permissionDecision": "allow"}
    elif action in ['deny', 'ask']:
        payload = {"permissionDecision": action, "permissionDecisionReason": reason}
    elif action == 'block':
        payload = {"decision": "block", "reason": reason}
    elif action == 'approve':
        payload = {"decision": "approve"}

    if context:
        payload["additionalContext"] = context

    if event:
        payload["hookSpecificOutput"] = {"hookEventName": event, **payload}

    return DecisionResponse(payload=payload, blocked=blocked)

# 保持公共 API 兼容性
def allow(self, **kwargs) -> DecisionResponse:
    return self._build_response('allow', **kwargs)

def deny(self, reason: str, **kwargs) -> DecisionResponse:
    return self._build_response('deny', reason=reason, blocked=True, **kwargs)
```

### Phase 2: ConfigManager 整合簡化 (中優先級)

#### ✅ Step 5: 簡化政策載入 (目標：-25 行)
**當前代碼 (lines 495-525, 30 行):**
```python
def _load_policy(self) -> Dict[str, Any]: ...
def _merge_policy(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]: ...
```

**替換為 (目標：~5 行):**
```python
def _load_simple_policy(self) -> Dict[str, Any]:
    user_policy = self.config_manager.get('decision_policy', {})
    # 簡單字典合併，避免深度遞歸
    result = deepcopy(_DEFAULT_POLICY)
    for section, rules in user_policy.items():
        if section in result and isinstance(rules, dict):
            result[section].update(rules)
        else:
            result[section] = rules
    return result
```

#### ✅ Step 6: 重構初始化方法
```python
def __init__(self, config_manager: ConfigManager = None, policy_path: Path = None):
    # 優先使用傳入的 config_manager
    self.config_manager = config_manager or ConfigManager.get_instance()
    self.policy = self._load_simple_policy()
    self._compiled_rules = self._compile_rules(
        self.policy.get("pre_tool_use", {}).get("rules", [])
    )
```

### Phase 3: 驗證與測試 (高優先級)

#### ✅ Step 7: 功能驗證
- [ ] **基本功能測試:**
  ```bash
  cd .claude/hooks
  uv run python -c "from utils.decision_api import DecisionAPI; api = DecisionAPI(); print('✅ Import successful')"
  ```

- [ ] **決策邏輯測試:**
  ```python
  # 測試危險命令檢測
  api = DecisionAPI()
  result = api.pre_tool_use_decision("Bash", {"command": "rm -rf /"})
  assert result.blocked == True

  # 測試正常命令
  result = api.pre_tool_use_decision("Read", {"file_path": "test.txt"})
  assert result.blocked == False
  ```

- [ ] **整合測試:** `uv run python tests/test_integration_verification.py`

#### ✅ Step 8: 性能驗證
```python
import time
api = DecisionAPI()

# 測試初始化時間 (目標 < 10ms)
start = time.time()
api2 = DecisionAPI()
init_time = (time.time() - start) * 1000
print(f"初始化時間: {init_time:.2f}ms")

# 測試決策時間 (目標 < 1ms)
start = time.time()
result = api.pre_tool_use_decision("Bash", {"command": "ls -la"})
decision_time = (time.time() - start) * 1000
print(f"決策時間: {decision_time:.2f}ms")
```

## 🔍 程式碼審查檢查點

### 複雜度指標
- [ ] **行數減少**: 570 → ~300 行 (目標 -47%)
- [ ] **類別數量**: 5 → 2 類別 (移除 TagDefinition, TagMatcher, _CompiledRule)
- [ ] **方法數量**: 25+ → ~15 方法
- [ ] **嵌套深度**: 減少至 3 層以內

### 功能完整性
- [ ] 所有公共方法簽名保持不變
- [ ] 決策邏輯結果一致
- [ ] ConfigManager 整合正常工作
- [ ] 錯誤處理機制保留

### 效能指標
- [ ] 初始化時間 < 10ms
- [ ] 單次決策時間 < 1ms
- [ ] 記憶體使用量未增加

## 🚨 風險控制

### 回滾計劃
```bash
# 如果出現問題，立即回滾
git checkout .
cp utils/decision_api.py.backup utils/decision_api.py
```

### 測試策略
1. **重構前**: 執行完整測試套件，記錄基準結果
2. **重構中**: 每個步驟後執行基本功能測試
3. **重構後**: 執行完整測試套件，比較結果

### 關鍵驗證點
- [ ] Herald CLI 仍可正常執行: `uv run herald.py --hook Notification --json-only`
- [ ] 危險命令仍被正確攔截
- [ ] ConfigManager 整合功能正常
- [ ] 所有 hook 模組可正常載入 DecisionAPI

## 📊 成功標準

**必須達成 (MUST):**
- [ ] 所有現有測試通過
- [ ] 程式碼行數減少 40% 以上
- [ ] 公共 API 兼容性 100%
- [ ] 無功能性回歸

**期望達成 (SHOULD):**
- [ ] 初始化效能提升 20%
- [ ] 決策效能維持或改善
- [ ] 程式碼可讀性提升

**額外收穫 (COULD):**
- [ ] 記憶體使用量降低
- [ ] 更容易編寫單元測試
- [ ] 更清晰的錯誤訊息

---

**實作者注意事項:**
1. 每完成一個 Phase 就提交一次程式碼
2. 有疑問請參考 `decision_api.py.backup` 原始實作
3. 測試失敗時立即停止，檢查問題
4. 保持向後兼容性是最高優先級

*生成時間: 2025-09-24 - Herald System Phase 2 優化*