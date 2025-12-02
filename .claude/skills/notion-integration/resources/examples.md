# Notion Integration Examples

常見使用情境範例。

## 情境 1：開始新專案

當在新資料夾開始專案時：

```bash
# 1. 確認專案狀態
uv run python scripts/notion/cli.py project info

# 2. 在 Notion 建立專案
uv run python scripts/notion/cli.py project create -d "專案描述"
```

## 情境 2：規劃功能任務

規劃新功能時建立任務：

```python
from scripts.notion import NotionClient, ProjectManager, TaskManager
from scripts.notion.tasks import TaskDefinition, TaskPriority, TaskType

tasks = [
    TaskDefinition(
        name="設計 API 規格",
        summary="定義 REST API endpoints",
        priority=TaskPriority.HIGH,
        task_type=TaskType.FEATURE,
        estimated_hours=2,
    ),
    TaskDefinition(
        name="實作 API endpoints",
        summary="根據規格實作",
        priority=TaskPriority.HIGH,
        task_type=TaskType.FEATURE,
        estimated_hours=4,
    ),
    TaskDefinition(
        name="撰寫測試",
        summary="API 單元測試",
        priority=TaskPriority.MEDIUM,
        task_type=TaskType.TEST,
        estimated_hours=2,
    ),
]

with NotionClient() as client:
    pm = ProjectManager(client)
    tm = TaskManager(client, pm)

    project_id, _ = pm.get_or_create_project()
    result = tm.create_tasks_batch(tasks, project_id)

    print(f"建立 {result.success_count} 個任務")
```

## 情境 3：設定任務依賴

```python
dependencies = {
    "實作 API endpoints": ["設計 API 規格"],
    "撰寫測試": ["實作 API endpoints"],
}

result = tm.update_task_dependencies(dependencies, project_id)
```

## 情境 4：快速查看任務

```bash
uv run python scripts/notion/cli.py tasks list
```

輸出範例：
```
============================================================
📋 任務列表 - claude-code-hooks-herald
============================================================
找到 3 個任務:

  ✅ [High] 設計 API 規格
  🔵 [High] 實作 API endpoints
  ⚪ [Medium] 撰寫測試
```

## 情境 5：從 Slash Command 使用

```
/notion-sync           # 同步專案
/notion-task 實作登入功能  # 快速建立任務
```
