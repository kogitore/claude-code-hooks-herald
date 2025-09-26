---
id: 0001
status: accepted
date: 2025-09-18
related: []
---

> **[English Version](./0001-audio-mapping.md)**

# 決策：音效對應策略

## 背景
- Claude Code 僅支援官方事件（`Stop`, `SubagentStop`, `Notification`）。
- 每個事件需要對應音效，同時避免在 Python 內寫死路徑。
- 必須保留向後兼容能力，以支援舊有別名與未來擴充。

## 方案比較
1. **程式內硬編碼**：設定簡單但難以依專案覆寫。
2. **檔名約定（如 `stop.wav`）**：命名含糊，複數版本時不易辨識。
3. **外部設定檔（JSON/YAML）**：維持程式精簡並允許使用者自訂。

## 決策
採用 JSON 設定檔（`.claude/hooks/utils/audio_config.json`）管理官方事件與語意化檔名的對應。載入時進行別名正規化（`stop`, `agent-stop` 等），並提供 `SubagentStop → Stop` 的回退機制。

## 影響
- **正向**：清楚區隔程式與設定；使用者可安全替換音效；支援舊別名。
- **取捨**：增加設定層需要處理檔案缺失與錯誤回報。

## 實作重點
- `AudioManager` 讀取 `audio_config.json`，預設從 `.claude/sounds/` 解析音效。
- `_canonical_audio_key()` 完成大小寫與別名的正規化。
- 回退鏈：`SubagentStop → Stop` 確保無自訂檔案時仍有音效。
- 單元測試涵蓋別名與錯誤日誌（`.claude/hooks/tests/test_audio_played_and_timeout.py` 等）。

## 參考
- `.claude/hooks/utils/audio_config.json`
- `.claude/hooks/utils/audio_manager.py`
- `.claude/hooks/tests/test_audio_played_and_timeout.py`
