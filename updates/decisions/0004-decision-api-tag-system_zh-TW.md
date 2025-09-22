---
id: 0004
status: proposed
date: 2025-09-18
related: [0003]
---

> **[English Version](./0004-decision-api-tag-system.md)**

# 決策：基於標籤的 Decision API 與嚴重性分級

## 背景
目前的 DecisionAPI 需要使用者手動編寫正則表達式，容易出錯且不夠友善。雖然 `decision_policy.example.json` 包含 `tags` 欄位，但 DecisionAPI 並未使用。團隊經常需要相同的模式（套件管理器、git 操作、檔案權限），但在正則語法上遇到困難。

## 問題
1. **入門門檻高** - 使用者必須理解正則表達式才能自訂策略
2. **模式重複** - 常見情境（npm install、git reset、機密檔案）需要手動寫正則
3. **無嚴重性系統** - 所有違規都被同等對待
4. **維護負擔** - 當新工具出現時，正則模式需要更新

## 提議解決方案
擴展 DecisionAPI，加入基於標籤的系統，將常見模式抽象為語意化標籤，同時保留正則表達式的彈性供進階使用者使用。

### 標籤分類與內建模式

```python
BUILT_IN_TAG_PATTERNS = {
    # 套件管理
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

    # Git 操作
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

    # 系統操作
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

    # 檔案類型
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

### 增強的規則定義

```json
{
  "pre_tool_use": {
    "rules": [
      {
        "tags": ["system:dangerous"],
        "action": "deny",
        "severity": "critical",
        "reason": "阻擋破壞性系統指令"
      },
      {
        "tags": ["package:install", "system:admin"],
        "action": "ask",
        "severity": "medium",
        "reason": "需要提升權限安裝套件"
      },
      {
        "pattern": "custom\\.regex",
        "action": "deny",
        "severity": "high",
        "reason": "進階使用者的自訂模式"
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

### API 實作

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
```

## 向後相容性
- 現有基於正則的規則繼續正常運作
- 標籤是附加的 - 規則可以同時包含 `pattern` 和 `tags`
- 內建標籤模式可在使用者策略中覆寫
- 嚴重性是選用的，預設為 "medium"

## 遷移路徑
1. **階段 1**：在現有正則基礎上實作標籤系統
2. **階段 2**：更新 `decision_policy.example.json` 加入標籤範例
3. **階段 3**：撰寫正則 → 標籤的遷移指南
4. **階段 4**：新增 CLI 工具建議常見模式的標籤

## 優勢
- **降低門檻**：使用者寫 `"tags": ["package:install"]` 而非複雜正則
- **一致性**：跨團隊和專案的標準模式
- **可擴展性**：新工具模式透過更新加入內建清單
- **彈性**：進階使用者仍可在需要時使用自訂正則
- **優先級**：嚴重性分級允許精細的策略控制

## 實作檢查清單
- [ ] 擴展 `_CompiledRule` 加入 tags 和 severity
- [ ] 實作 `TagMatcher` 類別
- [ ] 更新 `_compile_pre_rules` 處理標籤
- [ ] 新增嚴重性閾值解析
- [ ] 更新測試涵蓋標籤匹配
- [ ] 更新文檔和範例
- [ ] 新增標籤探索的 CLI 工具

## 參考
- 當前：`.claude/hooks/utils/decision_api.py`
- 樣板：`.claude/hooks/utils/decision_policy.example.json`
- 相關：ADR-0003（決策策略樣板）