---
name: notion-integration
description: Notion 專案與任務管理整合指引
version: "1.0"
---

# Notion Integration Skill

將 Claude Code 專案與 Notion 整合的指引。

## 核心原則

**專案名稱自動偵測**: 使用資料夾名稱作為 Notion 專案名稱（如 `claude-code-hooks-herald`）

## 可用工具

所有功能都透過 `.claude/herald/notion/` 模組實作：

### CLI 指令

```bash
# 查看當前專案狀態
uv run python .claude/herald/notion/cli.py project info

# 在 Notion 建立/取得專案
uv run python .claude/herald/notion/cli.py project create

# 列出專案任務
uv run python .claude/herald/notion/cli.py tasks list

# 互動式建立任務
uv run python .claude/herald/notion/cli.py tasks create
```

### Python API

```python
# 從 .claude/herald 目錄導入
import sys
sys.path.insert(0, ".claude/herald")

from notion import NotionClient, ProjectManager, TaskManager
from notion.tasks import TaskDefinition, TaskPriority

with NotionClient() as client:
    # 自動偵測專案
    pm = ProjectManager(client)
    project_id, created = pm.get_or_create_project()

    # 建立任務
    tm = TaskManager(client, pm)
    task = TaskDefinition(
        name="實作新功能",
        summary="功能描述",
        priority=TaskPriority.HIGH,
    )
    tm.create_task(task, project_id)
```

## Slash Commands

- `/notion-sync` - 同步專案狀態到 Notion
- `/notion-task` - 快速建立任務

## 環境設定

需要在 `.env` 設定：

```bash
NOTION_API_TOKEN=secret_xxx          # 必填
NOTION_PROJECT_DATABASE_ID=xxx       # 專案資料庫
NOTION_TASK_DATABASE_ID=xxx          # 任務資料庫
```

詳見 `.env.example`

## 使用時機

當使用者提到：
- 「建立任務」、「新增任務」
- 「同步 Notion」、「更新專案」
- 「專案管理」、「任務追蹤」

## 相關資源

- [使用範例](resources/examples.md)
- [CLI 原始碼](../../herald/notion/)
- [.env.example](../../../.env.example)
