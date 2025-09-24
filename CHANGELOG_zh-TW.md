# Changelog

本專案的所有重要變更會記錄在此檔案。格式遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) 並採用 [Semantic Versioning](https://semver.org/)。

提交訊息建議遵循 [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)。

## [Unreleased]

## [0.4.0-dev] - 2025-09-24
### 🔥 重大系統簡化 - Linus 風格架構清理

**「你們這些人到底他媽的有什麼毛病？用了20+個檔案來做事件發生時播放聲音，變成了一個無法閱讀的鼠窩垃圾堆。這已經修好了。」** - *Linus 評價*

#### **問題所在**：企業級 Java 地獄
- **40+ Python 檔案**做本應簡單的音效通知系統
- **複雜抽象層**：MiddlewareRunner、HandlerRegistry、AudioDispatcher
- **過度工程化**：多個類別、註冊器和中間件處理基本功能
- **技術債務**：重複代碼、無用抽象、理論邊緣情況

#### **解決方案**：殘酷簡化

##### **階段 1：移除抽象地獄**
###### 刪除
- ❌ **`middleware_runner.py`** - 不必要的中間件執行引擎
- ❌ **`handler_registry.py`** - 為8個事件類型建立的註冊器模式廢話
- ❌ **`audio_dispatcher.py`** - AudioManager 上的又一層抽象
- ❌ **`base_hook.py`** - 無用抽象，返回空字典
- ❌ **`dispatch_types.py`** - 簡單操作的類型劇場
- ❌ **`session_storage.py`**（然後在需要時重新建立）- 簡化會話管理
- ❌ **`subagent_stop.py`** - stop.py 的完全相同重複

###### 變更
- **Herald Dispatcher**：從500+行企業複雜度變為**直接字典查找**
- **事件處理**：從中間件→註冊器→處理器鏈變為**簡單函數調用**
- **音效邏輯**：從多層分派變為**直接 AudioManager 整合**
- **Stop 事件**：合併重複邏輯到共享處理器的單一實現

##### **階段 2：測試套件清理**
###### 移除（消除 9 個檔案）
- ❌ **`test_middleware_runner.py`** - 測試已刪除的功能
- ❌ **`test_handler_registry.py`** - 測試已刪除的抽象
- ❌ **`test_audio_dispatcher.py`** - 測試已移除的層
- ❌ **`test_decision_api_refactor.py`** - 重複測試邏輯
- ❌ **`test_constants.py`** - 測試常數定義（毫無意義）
- ❌ **`test_json_only.py`** - 簡單相容性測試
- ❌ **`test_throttle.py`** - 邏輯整合到主測試中
- ❌ **`test_subagent_stop.py`** - stop 測試的重複
- ❌ **`run_tests.py`** - 不必要的測試執行器（直接使用 pytest）

###### 結果
- **測試檔案**：19 → 8 檔案（-58% 減少）
- **測試代碼**：1,772 → 674 行（-62% 減少）
- **測試重點**：移除邊緣情況測試，保留核心功能驗證

##### **階段 3：檔案系統清理**
###### 移除暫存/開發檔案
- ❌ **`temp_test_config_dir/`** - 暫存測試配置目錄
- ❌ **`test_audio_basic.py`** - 開發音效測試腳本
- ❌ **`test_audio_threading.py`** - 開發線程測試
- ❌ **`*.backup`** 檔案 - 開發備份檔案
- ❌ **`*.example`** 檔案 - 不必要的範例配置

### **結果：從企業地獄到可工作代碼**

#### **檔案數量減少**
- **主要檔案**：20+ → 14 檔案（-30%）
- **測試檔案**：19 → 8 檔案（-58%）
- **工具檔案**：10+ → 6 檔案（-40%）
- **專案總計**：40+ → 22 檔案（-45%）

#### **代碼簡化**
- **Herald Dispatcher**：直接字典查找，沒有中間件廢話
- **事件處理**：函數調用而非類別階層
- **音效系統**：直接使用 AudioManager，沒有額外層
- **Stop 邏輯**：單一實現處理 Stop 和 SubagentStop

#### **可維護性提升**
- **可讀代碼**：初級開發人員可以理解流程
- **簡單除錯**：沒有複雜中間件鏈需要追蹤
- **快速變更**：修改需要分鐘而非小時
- **清晰架構**：8 個 hooks + 6 個 utils + 8 個測試 = 完成

#### **效能影響**
- **啟動時間**：更快初始化（更少匯入，更少物件建立）
- **執行路徑**：直接函數調用 vs. 多層委派
- **記憶體使用**：消除不必要物件階層
- **音效播放**：修正節流配置衝突

### **通過清理存活的部分**
#### **必要主檔案**（8 個）
- ✅ `herald.py` - 核心分派器（大幅簡化）
- ✅ `notification.py`, `stop.py`, `pre_tool_use.py`, `post_tool_use.py`
- ✅ `user_prompt_submit.py`, `session_start.py`, `session_end.py`

#### **必要工具**（6 個）
- ✅ `audio_manager.py` - 做實際工作（播放聲音）
- ✅ `decision_api.py` - 安全決策（實際需要）
- ✅ `config_manager.py` - 配置（被其他工具使用）
- ✅ `common_io.py`, `constants.py`, `session_storage.py`

#### **必要測試**（8 個）
- ✅ 每個 hook 的核心功能測試
- ✅ Herald dispatcher 整合測試
- ✅ 音效系統驗證

### **Linus 判決**
**之前**：「*這個代碼庫在各個方面都是完全徹底的災難*」
**之後**：「*這個可以。22個檔案，職責清晰，沒有廢話，專注測試。代碼不再是屎，已經修好了。*」

### **重大變更**
- 無。**100% 向後兼容性**維持
- 所有現有 `--hook` 指令運行相同
- 配置檔案不變
- 音效功能完全保留

### **移除檔案**
- **9 個抽象層檔案** - middleware_runner.py、handler_registry.py、audio_dispatcher.py 等
- **9 個測試檔案** - 移除冗餘和過度工程測試
- **5+ 個暫存檔案** - 清理開發人工製品
- **多個備份檔案** - 移除 .backup 和 .example 檔案

## [0.3.0-dev] - 2025-09-24
### 🔧 初始架構評估和準備

#### **發現階段**
##### **代碼庫分析**
- **識別過度工程化**：發現20+個檔案實現基本音效通知系統
- **架構問題**：發現多個不必要抽象層
- **代碼重複**：發現 stop.py 和 subagent_stop.py 完全相同
- **測試膨脹**：識別19個測試檔案具有顯著冗餘

##### **效能基準**
- **執行路徑分析**：追蹤複雜的中間件→註冊器→處理器鏈
- **音效系統檢查**：發現可工作的 AudioManager 被埋在抽象層下
- **配置問題**：發現 herald.py 和 audio_config.json 之間的節流設定衝突

#### **規劃和準備**
##### **新增（開發工具）**
- **架構分析檔案**：HOOKS_ARCHITECTURE.md、HOOKS_ARCHITECTURE_Linus_fix.md
- **清理指引**：詳細的逐步簡化計劃
- **Linus 評價模式**：殘酷誠實評估方法

##### **修正（關鍵問題）**
- **音效節流衝突**：修正 herald.py 中的 DEFAULT_THROTTLE_WINDOWS 以匹配 audio_config.json（600s → 120s）
- **缺失任務完成音效**：解決阻止完成聲音播放的節流問題
- **匯入依賴**：修正清理後的 session_storage 匯入問題

#### **評估結果**
##### **識別待移除**
- **抽象層**：7+ 個不必要的工具檔案
- **重複邏輯**：多個相同實現
- **過度測試**：50%+ 的測試覆蓋理論邊緣情況
- **暫存檔案**：開發人工製品和備份檔案

##### **標記保留**
- **核心功能**：8個必要 hook 處理器
- **可工作系統**：AudioManager、DecisionAPI、ConfigManager
- **必要測試**：核心功能和整合測試

### **準備完成**
- **備份建立**：重大重構前完整系統備份
- **計劃記錄**：建立全面清理策略
- **工具就緒**：準備分析和指導文檔
- **評估完成**：清楚理解什麼可工作 vs. 什麼是膨脹

此版本代表重大 v0.4.0 簡化工作前的*規劃和評估階段*。

## [0.2.0] - 2025-09-22
### 新增
- **完整 Claude Code 事件支援**：實現 8/9 官方事件（UserPromptSubmit、PreToolUse、PostToolUse、SessionStart、SessionEnd）
- **Claude Code 欄位兼容性**：完全支援傳統（`tool`/`toolInput`）和標準（`tool_name`/`tool_input`）欄位格式
- **全面測試套件**：增強測試覆蓋，9個通過測試，包括欄位優先級和錯誤處理場景
- **Decision API 安全**：進階安全策略，具備指令模式匹配、檔案保護和套件安裝驗證
- Herald 分派器（`.claude/hooks/herald.py`），整合 Decision API 用於 Pre/PostToolUse 和 Stop 事件
- BaseHook 框架加上 Notification/Stop/SubagentStop 實現，重複使用共享音效處理
- 可配置 `decision_policy.json`（含 `decision_policy.example.json` 範本 + ADR 0003）擴展 allow/deny/ask/block 規則，無需失去內建保護措施
- TagMatcher 函式庫（`system:dangerous`、`package:install`、`git:destructive` 等），具備嚴重性排名的策略回應；ADR 0004 記錄設計

### 變更
- **欄位擷取邏輯**：增強 `_extract_tool()` 和 `_extract_tool_input()` 方法，支援 Claude Code 標準欄位名稱
- **測試基礎設施**：新增直接 hook 測試工具（`_invoke_pre_tool_use_direct`）和決策解析幫助器
- **路線圖修正**：更新路線圖 v1.6 以反映實際 8/9 事件完成狀態，移除非官方 Error 事件
- `.claude/settings.json` 現在將所有官方事件路由透過 Herald 分派器
- README（EN/繁中）更新描述分派器架構、Decision API 和 CLI 使用方式

### 修正
- **關鍵工具阻擋問題**：解決 Claude Code 欄位名稱不匹配導致工具即使獲得許可仍被錯誤阻擋
- **JSON 輸出格式**：確保完全符合 Claude Code hook 結構描述要求
- **錯誤處理**：無效 JSON 輸入的優雅降級，同時維持 hook 功能
- 確保 CLI hooks 發出最少 JSON（`{"continue": true}`），遙測保留在 stderr

### 安全
- **增強 PreToolUse 安全**：新增危險指令模式匹配（`rm -rf`、`shutdown` 等）
- **敏感檔案保護**：自動偵測和阻擋對 `.env`、金鑰檔案和認證的操作
- **套件安裝守衛**：`npm install`、`pip install` 和類似操作需要人工確認

### 移除
- **非官方事件支援**：移除 Error 事件實現以符合 Claude Code 官方規格（僅 9 個事件）

---

## [0.1.0] - 2025-09-18
### 新增
- **通知聲音**：為用戶提示/通知播放音效提示
- **任務完成聲音**：工具/任務完成的專用音效
- **子代理完成聲音**：子代理成功的單獨音效
- **智慧節流**：基於時間戳的快取避免音效垃圾訊息
- **本地音效檔案**：純粹在本地 `.wav` 資產上運作，無需 API 金鑰
- **跨平台支援**：macOS (afplay)、Linux (ffplay/aplay)、Windows (winsound)
- **音量控制**：macOS/Linux 透過播放器參數，Windows 透過記憶體處理
- **配置系統**：`.claude/hooks/utils/audio_config.json` 管理音量、路徑、映射
- **測試框架**：`uv run` + `pytest` 腳本，具備 `AUDIO_PLAYER_CMD` 覆蓋

### 音效
- 預設聲音映射：`task_complete.wav` (Stop)、`agent_complete.wav` (SubagentStop)、`user_prompt.wav` (Notification)
- 節流視窗：Stop/SubagentStop (120s)、Notification (30s)
- 預設音量：0.2 (20%)

### 平台支援
- **Windows**：Python stdlib `winsound` + `audioop` 進行音量縮放
- **macOS**：`afplay` CLI 配合 `-v` 音量參數
- **Linux**：支援 `ffplay` (`-volume`) 和 `aplay`

[0.1.0]: https://github.com/kogitore/claude-code-hooks-herald