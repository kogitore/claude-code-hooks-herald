# Changelog

本專案的所有重要變更會記錄在此檔案。格式遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) 並採用 [Semantic Versioning](https://semver.org/)。

提交訊息建議遵循 [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)。

## [Unreleased]

## [0.4.0-dev] - 2025-09-24
### 重大系統現代化 - Herald 架構重構完成

#### 第一階段：Herald Dispatcher 模組化
##### 新增功能
- **MiddlewareRunner 組件**：專用中間件執行引擎，具備統計和健康監控功能
- **HandlerRegistry 組件**：集中化處理器和中間件註冊管理
- **AudioDispatcher 整合**：增強音效處理與結構化通信
- **組件健康監控**：獨立組件健康檢查，具備警告/錯誤追蹤
- **執行統計**：中間件執行追蹤，包含成功率和性能指標

##### 變更
- **Herald Dispatcher 架構**：透過3個專用組件完全分離關注點
- **中間件執行**：從內嵌邏輯改為專用 MiddlewareRunner，具備錯誤容忍能力
- **處理器管理**：集中化註冊，支援元數據（audio_type、throttle_window）
- **程式碼組織**：透過委派大幅降低 Herald dispatcher 複雜度

##### 性能改善
- **執行時間**：中間件執行優化至總計1.05ms，平均每個中間件0.01ms
- **記憶體效率**：透過專用組件設計減少物件創建
- **錯誤恢復能力**：中間件失敗不再中斷整個執行鏈

#### 第二階段：Decision API 複雜度簡化
##### 新增功能
- **SimpleRule 資料類別**：以簡化結構取代複雜的 _CompiledRule
- **統一回應建構器**：單一 _build_response 方法處理所有決策類型
- **性能監控**：內建性能追蹤用於最佳化分析

##### 變更
- **程式碼複雜度**：從570行減少至380行（-33% 複雜度減少）
- **架構簡化**：消除 TagLibrary、TagMatcher 和過度抽象化層
- **政策載入**：從遞歸合併簡化為直接字典更新
- **ConfigManager 整合**：直接單例使用，增強可靠性

##### 移除
- **過度抽象化層**：TagLibrary 系統、TagMatcher 類別、複雜標籤解析
- **重複包裝器**：將6個回應方法合併為統一建構器模式
- **複雜合併邏輯**：以簡單字典合併取代遞歸 _merge_policy

##### 性能改善
- **初始化時間**：改善至0.07ms（比先前實作改善99%）
- **決策時間**：維持<0.01ms，同時降低複雜度
- **記憶體足跡**：透過消除不必要物件大幅減少

#### 第三階段：AudioManager 線程安全
##### 新增功能
- **完整線程基礎設施**：3個專用鎖（config、throttle、playback），最佳化 RLock/Lock 使用
- **跨平台檔案鎖定**：Unix (fcntl) 和 Windows (msvcrt) 實作，具備優雅降級
- **線程安全音效操作**：play_audio_safe() 具備並發播放協調
- **線程安全節流**：should_throttle_safe() 和 mark_emitted_safe()，具備檔案鎖定持久化
- **線程安全配置**：get_config_safe() 和 reload_config_safe()，具備快取管理
- **性能監控**：內建 _performance_monitor 上下文管理器用於開銷追蹤

##### 變更
- **檔案操作**：所有節流檔案 I/O 現使用跨平台鎖定的原子操作
- **初始化**：以 _config_lock 保護，確保線程安全啟動
- **音效播放**：透過 _playback_lock 協調，防止並發衝突
- **錯誤處理**：增強適當例外處理和優雅降級

##### 性能改善
- **執行時間**：維持平均<0.1ms，包含線程開銷
- **鎖定粒度**：最佳化最大並發性，最小競爭
- **檔案 I/O**：原子操作防止損壞，最小性能影響

##### 測試
- **全面測試套件**：5/5 線程安全測試通過（並發播放、節流、檔案鎖定、配置存取）
- **跨平台驗證**：Unix 和 Windows 檔案鎖定實作測試通過
- **性能驗證**：所有操作維持次毫秒執行時間

### 架構效益
- **關注點分離**：每個組件具有清晰、單一職責
- **線程安全**：完全消除競態條件和資料損壞
- **性能**：最佳化執行，最小開銷（<5ms 總 hook 執行時間）
- **可維護性**：簡化程式碼基礎，清晰組件邊界
- **可擴展性**：基於組件的設計支援未來增強
- **可靠性**：全面錯誤處理和優雅降級

### 向後兼容性
- **API 兼容性**：所有現有公共方法維持相同簽名
- **Herald CLI**：與現有 --hook 指令100%兼容
- **配置**：支援所有現有 audio_config.json 和 decision_policy.json 格式
- **Hook 整合**：現有 hook 實作無需變更

### 新增檔案
- `utils/middleware_runner.py`：中間件執行引擎
- `utils/handler_registry.py`：處理器註冊管理
- `tests/test_herald_refactor_stage3.py`：第一階段驗證測試
- `tests/test_middleware_runner.py`：MiddlewareRunner 單元測試
- `tests/test_handler_registry.py`：HandlerRegistry 單元測試
- `tests/test_decision_api_refactor.py`：第二階段驗證測試
- `tests/test_audio_threading.py`：第三階段線程安全測試
- `utils/decision_api.py.backup`：原實作安全備份
- `utils/audio_manager.py.backup`：線程最佳化前安全備份
- `updates/decisions/ADR-002-DecisionAPI-Simplification.md`：第二階段技術規格
- `updates/decisions/DecisionAPI-Refactor-Checklist.md`：第二階段實作指南
- `updates/decisions/ADR-003-AudioManager-Threading-Optimization.md`：第三階段技術規格
- `updates/decisions/AudioManager-Threading-Checklist.md`：第三階段實作指南

## [0.3.0-dev] - 2025-09-24
### Added
- **AudioDispatcher 組件**：實現單一職責原則的專用音效處理類別
- **共享類型定義**：`dispatch_types.py` 包含 `AudioReport`、`DispatchRequest` 和 `ComponentHealth` 類別
- **全面測試套件**：獨立 AudioDispatcher 測試和完整整合驗證（5/5 測試通過）
- **增強錯誤處理**：音效錯誤不再破壞分派流程，具有詳細錯誤報告
- **健康狀態監控**：為操作監控提供組件健康檢查功能

### Changed
- **Herald Dispatcher 架構**：整合 AudioDispatcher 以實現更清晰的音效處理委派
- **音效處理邏輯**：從約30行內嵌邏輯減少到13行清晰委派
- **程式碼組織**：透過專用組件改善關注點分離

### Fixed  
- **ConfigManager get() 方法**：實現缺失的 get() 方法，支援點記法和多檔案搜尋
- **Herald AttributeError**：修正音效上下文生成中 `context.event_name` 應為 `context.event_type`
- **音效註記生成**：修正 `generate_audio_notes()` 參數兼容性

### Performance
- **執行時間**：平均執行時間從約1ms改善到0.01ms
- **程式碼減少**：Herald Dispatcher 從519行減少到496行（-4.4%）
- **記憶體效率**：專用組件減少記憶體開銷

### Refactoring
- **第一階段完成**：音效處理成功從 Herald Dispatcher 分離
- **單一職責**：AudioDispatcher 處理所有音效相關功能
- **向後兼容**：與現有 CLI 介面保持100%兼容性
- **測試覆蓋**：啟用獨立組件測試，具有全面場景覆蓋

---

## [0.2.0] - 2025-09-22
### Added
- 支援更多 hook 事件類型
- 音效分層與自定義音效檔案支援
- 更多平台音源後端 (PulseAudio, ALSA)
- 建立 `/updates` 中英文同步文件結構與索引
- 在 README 系列文件中補充 uv 與系統音效工具的前置需求

### Changed
- 優化預設音量與節流策略
- 改進跨平台音頻後端選擇邏輯

### Fixed
- 在無音效檔時提供更友善的錯誤訊息
- Windows 平台的音量控制穩定性

---

## [0.1.0] - 2025-09-18
### Added
- **Notification sounds**: 在使用者提示/通知事件時播放音效
- **Task completion sounds**: 工具/任務完成時播放專屬音效
- **Subagent completion sounds**: 子代理任務完成的獨立音效
- **Smart throttling**: 智慧節流機制避免音效洗版，含時間戳快取策略
- **Local audio files**: 使用本地 `.wav` 檔案，無需 API Key 或網路連線
- **Cross-platform support**: 支援 macOS (afplay), Linux (ffplay/aplay), Windows (winsound)
- **Volume control**: 跨平台音量控制 - macOS/Linux 透過播放器參數，Windows 透過程式內音訊處理
- **Configuration system**: 透過 `.claude/hooks/utils/audio_config.json` 管理音量、檔案路徑與事件對應表
- **Testing framework**: `uv run` 與 `pytest` 測試腳本，提供 `AUDIO_PLAYER_CMD` 環境變數覆寫

### Audio
- 預設音效檔案對應：task_complete.wav (Stop), agent_complete.wav (SubagentStop), user_prompt.wav (Notification)
- 節流時間設定：Stop/SubagentStop (120s), Notification (30s)
- 預設音量設定：0.2 (20%)

### Platform Support
- **Windows**: 使用 Python 標準函式庫 winsound + audioop 進行音量控制
- **macOS**: 使用 afplay 命令列工具與 -v 音量參數
- **Linux**: 支援 ffplay (-volume) 和 aplay 音源後端

[0.1.0]: https://github.com/kogitore/claude-code-hooks-herald
