---
id: 0002
status: accepted
date: 2025-09-18
related: []
---

> **[English Version](./0002-throttling-strategy.md)**

# 決策：音效節流策略

## 背景
- Claude Code 在高頻操作時會重複觸發相同事件，造成音效洗版。
- Hook 每次呼叫都在獨立程序內執行，無法依賴記憶體快取。

## 方案比較
1. **記憶體節流**：實作容易，但程序重啟或多進程時立即失效。
2. **外部服務（Redis/SQLite）**：具持久性，但引入額外依賴與維運成本。
3. **檔案型 JSON 快取**：輕量、可檢查，並可跨程序共用。

## 決策
採用儲存在 `logs/audio_throttle.json` 的時間窗口節流。
- `Stop` / `SubagentStop`：以事件名為 key，節流 120 秒。
- `Notification`：以 `Notification:{sha1(message)[:12]}` 為 key，節流 30 秒，確保不同訊息仍可播放。
- 寫入時使用臨時檔原子交換，POSIX 平台額外加上 `fcntl` 檔案鎖。

## 影響
- **正向**：顯著降低重複音效；無需額外服務；可手動刪除檔案重置狀態。
- **取捨**：增加磁碟 I/O 並需要處理鎖；JSON 會隨時間變大，需定期清理。

## 實作重點
- `AudioManager.should_throttle()` 封裝節流邏輯。
- 使用 `pathlib.Path` 解決 `logs/` 寫入位置。
- 若鎖定失敗，記錄警告並以非節流模式繼續，避免阻塞 hook。

## 參考
- `.claude/hooks/utils/audio_manager.py`
- `.claude/hooks/tests/test_throttle.py`
- `logs/audio_throttle.json`（執行時產生）
