---
description: 同步當前專案到 Notion
---

同步當前專案狀態到 Notion。

## 執行步驟

1. **檢查專案狀態**
   ```bash
   uv run python .claude/herald/notion/cli.py project info
   ```

2. **如果專案不存在於 Notion**，建立它：
   ```bash
   uv run python .claude/herald/notion/cli.py project create
   ```

3. **列出現有任務**（如果專案已存在）：
   ```bash
   uv run python .claude/herald/notion/cli.py tasks list
   ```

4. **回報結果**，包含：
   - 專案名稱（使用資料夾名稱）
   - 專案 ID
   - 任務數量
   - 任務狀態摘要

## 錯誤處理

如果遇到 `NOTION_API_TOKEN is required` 錯誤：
- 請確認 `.env` 已設定 `NOTION_API_TOKEN`
- 參考 `.env.example` 設定範本
