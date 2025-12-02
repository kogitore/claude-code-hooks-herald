---
description: 快速建立 Notion 任務
argument-hint: 任務名稱 (例如: "實作登入功能")
---

快速建立一個 Notion 任務。

## 參數

`$ARGUMENTS` - 任務名稱

## 執行步驟

1. **解析任務資訊**
   - 任務名稱：`$ARGUMENTS`
   - 從名稱推斷優先級和類型（如包含 "fix" 可能是 Bug）

2. **確認專案存在**
   ```bash
   uv run python .claude/herald/notion/cli.py project info
   ```

   如果專案不存在，先建立：
   ```bash
   uv run python .claude/herald/notion/cli.py project create
   ```

3. **建立任務**

   使用 Python API 建立（更靈活）：
   ```python
   import sys
   sys.path.insert(0, ".claude/herald")

   from notion import NotionClient, ProjectManager, TaskManager
   from notion.tasks import TaskDefinition, TaskPriority, TaskType

   # 根據任務名稱推斷類型
   task_name = "$ARGUMENTS"

   # 簡單的類型推斷
   if any(kw in task_name.lower() for kw in ["fix", "bug", "修復"]):
       task_type = TaskType.BUG
       priority = TaskPriority.HIGH
   elif any(kw in task_name.lower() for kw in ["test", "測試"]):
       task_type = TaskType.TEST
       priority = TaskPriority.MEDIUM
   elif any(kw in task_name.lower() for kw in ["doc", "文件"]):
       task_type = TaskType.DOCS
       priority = TaskPriority.LOW
   else:
       task_type = TaskType.FEATURE
       priority = TaskPriority.MEDIUM

   with NotionClient() as client:
       pm = ProjectManager(client)
       tm = TaskManager(client, pm)

       task = TaskDefinition(
           name=task_name,
           priority=priority,
           task_type=task_type,
       )
       result = tm.create_task(task)
       print(f"✅ 任務已建立: {result['id']}")
   ```

   或使用互動式 CLI：
   ```bash
   uv run python .claude/herald/notion/cli.py tasks create
   ```

4. **回報結果**
   - 任務名稱
   - 任務 ID
   - 優先級
   - 類型

## 範例

```
/notion-task 實作用戶登入功能
/notion-task fix: 修復 API 錯誤處理
/notion-task 撰寫 README 文件
```
