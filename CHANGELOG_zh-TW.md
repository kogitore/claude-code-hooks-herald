# Changelog

本專案的所有重要變更會記錄在此檔案。格式遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) 並採用 [Semantic Versioning](https://semver.org/)。

提交訊息建議遵循 [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)。

## [Unreleased]
### Added
- 支援更多 hook 事件類型
- 音效分層與自定義音效檔案支援
- 更多平台音源後端 (PulseAudio, ALSA)
- 建立 `/updates` 中英文同步文件結構與索引

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
