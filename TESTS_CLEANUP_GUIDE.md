# 🧪 Tests 清理指引 - Linus 風格簡化

> **目標**: 將測試檔案從 19 個 (1772 行) 精簡到 8-10 個核心測試，專注於實際功能驗證

## 📊 現況分析

### 當前測試檔案 (19 個, ~1772 行)
```
✅ 核心功能測試 (保留)
├── test_herald_integration.py    # Herald 分派器整合測試
├── test_notification.py          # 通知 Hook 測試
├── test_stop.py                  # 停止 Hook 測試
├── test_pre_tool_use.py          # 工具前安全檢查
├── test_post_tool_use.py         # 工具後審計
├── test_user_prompt_submit.py    # 用戶輸入驗證

⚠️ 支援工具測試 (評估保留)
├── test_audio_threading.py       # 音效線程安全
├── test_decision_api.py          # 決策 API 基礎
├── test_config_manager.py        # 配置管理

❌ 重複/過時測試 (刪除)
├── test_decision_api_refactor.py # 重構測試版本 (重複)
├── test_audio_played_and_timeout.py # 特定音效測試
├── test_throttle.py              # 節流測試 (已整合到其他測試)
├── test_session_management.py    # 會話管理 (過度複雜)
├── test_json_only.py            # 相容性測試 (簡單)
├── test_constants.py            # 常數測試 (無意義)

🔧 框架/工具 (簡化)
├── common_test_utils.py          # 測試工具 (簡化)
├── conftest.py                   # pytest 配置
├── run_tests.py                  # 測試執行器
├── goal3_test.py                # 特定目標測試
```

## 🗑️ Phase 1: 立即刪除 (Priority 1)

### 重複和過時的測試
```bash
# 重複功能測試
rm .claude/hooks/tests/test_decision_api_refactor.py  # 與 test_decision_api.py 重複

# 微不足道的測試
rm .claude/hooks/tests/test_constants.py              # 測試常數定義沒意義
rm .claude/hooks/tests/test_json_only.py             # 簡單相容性測試

# 特定功能測試 (已整合到主測試)
rm .claude/hooks/tests/test_throttle.py              # 節流邏輯已在主測試中
rm .claude/hooks/tests/test_audio_played_and_timeout.py # 特定音效測試
```

**節省**: ~400-500 行代碼

## ⚠️ Phase 2: 評估合併 (Priority 2)

### 可能合併的測試
```bash
# 會話相關測試 - 檢查是否過度複雜
# 建議: 簡化 test_session_management.py 或與其他測試合併
test_session_management.py  # 6612 行 - 檢查是否有冗餘測試

# 特定目標測試 - 檢查是否還需要
goal3_test.py               # 特定重構目標測試，可能已過時
```

**潛在節省**: ~300-400 行代碼

## ✅ Phase 3: 保留和優化 (Priority 3)

### 絕對保留的核心測試 (8-10 個檔案)

#### **1. 核心分派測試**
```python
# test_herald_integration.py (保留)
# 測試: Herald 分派器整合、事件路由、錯誤處理
```

#### **2. Hook 功能測試 (5 個)**
```python
# test_notification.py (保留)
# test_stop.py (保留) - 包含 SubagentStop 邏輯
# test_pre_tool_use.py (保留) - 安全關鍵
# test_post_tool_use.py (保留) - 安全關鍵
# test_user_prompt_submit.py (保留) - 安全關鍵
```

#### **3. 支援系統測試 (2-3 個)**
```python
# test_audio_threading.py (保留) - 音效線程安全很重要
# test_decision_api.py (保留) - 安全決策核心
# test_config_manager.py (評估) - 如果配置複雜則保留
```

#### **4. 測試框架檔案 (2 個)**
```python
# conftest.py (簡化保留) - pytest 基礎配置
# common_test_utils.py (簡化保留) - 基本測試工具
```

## 🎯 具體執行步驟

### Step 1: 立即刪除 (由同事執行)
```bash
cd .claude/hooks/tests/

# 刪除重複和無意義測試
rm test_decision_api_refactor.py
rm test_constants.py
rm test_json_only.py
rm test_throttle.py
rm test_audio_played_and_timeout.py

echo "✅ Phase 1 完成: 刪除了 5 個無用測試檔案"
```

### Step 2: 評估特定檔案 (需要技術判斷)
```bash
# 檢查這些檔案的內容和必要性
file_to_check=(
    "test_session_management.py"  # 6612行 - 檢查是否過度測試
    "goal3_test.py"              # 特定重構測試
    "run_tests.py"               # 測試執行器 - 可能可以用 pytest 替代
)

# 對每個檔案進行評估:
for file in "${file_to_check[@]}"; do
    echo "=== 檢查 $file ==="
    head -20 "$file"
    echo ""
    wc -l "$file"
    echo "請判斷是否保留此檔案"
    echo ""
done
```

### Step 3: 簡化保留的檔案
```bash
# 簡化測試工具檔案
# common_test_utils.py - 移除不必要的輔助函數
# conftest.py - 保持最小配置
```

## 📋 清理檢查清單

### ✅ 執行後驗證
```bash
# 1. 檔案計數檢查
find .claude/hooks/tests -name "*.py" | wc -l
# 目標: 8-10 個檔案 (從 19 個減少)

# 2. 代碼行數檢查
wc -l .claude/hooks/tests/*.py | tail -1
# 目標: ~800-1000 行 (從 1772 行減少)

# 3. 功能測試
python -m pytest .claude/hooks/tests/ -v
# 確保核心功能測試通過
```

### 📊 成功指標
- **檔案數**: 19 → 8-10 個 (-50%)
- **代碼行數**: 1772 → ~900 行 (-50%)
- **測試覆蓋**: 保持核心功能 100% 覆蓋
- **執行時間**: 更快的測試執行

## 🚨 注意事項

### ❌ 不要刪除的測試
- **安全相關測試**: `test_pre_tool_use.py`, `test_post_tool_use.py`
- **核心功能測試**: `test_herald_integration.py`
- **線程安全測試**: `test_audio_threading.py`

### ⚠️ 謹慎處理
- **test_session_management.py**: 檢查是否有獨特的測試案例
- **test_config_manager.py**: 如果配置邏輯複雜，考慮保留
- **common_test_utils.py**: 簡化但不完全刪除

### ✅ 安全刪除
- 任何包含 "refactor", "verification", "goal" 的測試檔案
- 測試常數、簡單相容性功能的檔案
- 重複測試已存在功能的檔案

## 🎯 最終目標

**簡化前**:
```
tests/
├── 19 個測試檔案
├── 1772 行測試代碼
├── 複雜的測試依賴
└── 過度測試邊緣情況
```

**簡化後**:
```
tests/
├── 8-10 個核心測試檔案
├── ~900 行重點測試代碼
├── 簡潔的測試工具
└── 專注於實際功能驗證
```

**Linus 標準**: "測試應該驗證代碼工作，不是展示你會寫多少測試。**The tests should be shit-simple and just work.**"

---

*執行這個清理計劃，你的同事將會感謝你消除了測試代碼的冗餘和複雜性。*