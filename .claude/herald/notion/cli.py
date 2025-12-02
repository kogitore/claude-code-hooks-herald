#!/usr/bin/env python3
"""CLI entry point for Notion integration.

Usage:
    uv run python .claude/herald/notion/cli.py project info
    uv run python .claude/herald/notion/cli.py project create
    uv run python .claude/herald/notion/cli.py tasks list
    uv run python .claude/herald/notion/cli.py tasks create
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add herald directory for imports when run directly
if __name__ == "__main__":
    herald_root = Path(__file__).parent.parent
    if str(herald_root) not in sys.path:
        sys.path.insert(0, str(herald_root))

from notion.client import NotionClient, NotionConfig
from notion.project import ProjectInfo, ProjectManager
from notion.tasks import TaskManager


def cmd_project_info(args: argparse.Namespace) -> int:
    """Show current project information."""
    project = ProjectInfo.auto_detect()

    print("=" * 60)
    print("📁 專案資訊 (Auto-Detected)")
    print("=" * 60)
    print(f"名稱:     {project.name}")
    print(f"路徑:     {project.root_path}")
    print()

    # Check Notion connection
    try:
        config = NotionConfig.from_env()
        print("✅ Notion 配置已載入")

        with NotionClient(config) as client:
            pm = ProjectManager(client)
            existing = pm.find_project_by_name(project.name)

            if existing:
                print(f"✅ 專案已存在於 Notion")
                print(f"   ID: {existing['id']}")
            else:
                print("ℹ️  專案尚未建立於 Notion")
                print("   執行 'project create' 來建立")

    except ValueError as e:
        print(f"⚠️  {e}")
        print("   請設定 NOTION_API_TOKEN 環境變數")

    return 0


def cmd_project_create(args: argparse.Namespace) -> int:
    """Create or get current project in Notion."""
    project = ProjectInfo.auto_detect()

    if args.description:
        project.description = args.description

    print("=" * 60)
    print("🏗️  建立/取得專案")
    print("=" * 60)
    print(f"專案名稱: {project.name}")
    print()

    try:
        with NotionClient() as client:
            pm = ProjectManager(client)
            project_id, was_created = pm.get_or_create_project(project)

            if was_created:
                print(f"✅ 專案已建立!")
            else:
                print(f"✅ 專案已存在!")

            print(f"   ID: {project_id}")

    except ValueError as e:
        print(f"❌ 錯誤: {e}")
        return 1

    return 0


def cmd_tasks_list(args: argparse.Namespace) -> int:
    """List tasks for current project."""
    project = ProjectInfo.auto_detect()

    print("=" * 60)
    print(f"📋 任務列表 - {project.name}")
    print("=" * 60)

    try:
        with NotionClient() as client:
            pm = ProjectManager(client)
            existing = pm.find_project_by_name(project.name)

            if not existing:
                print("ℹ️  專案尚未建立於 Notion")
                print("   執行 'project create' 來建立")
                return 0

            project_id = existing["id"]
            tm = TaskManager(client, pm)
            tasks = tm.get_project_tasks(project_id)

            if not tasks:
                print("(無任務)")
                return 0

            print(f"找到 {len(tasks)} 個任務:\n")

            for task in tasks:
                name = client.extract_title(task, "Task name")
                props = task.get("properties", {})

                # Extract status
                status_prop = props.get("Status", {})
                status = status_prop.get("status", {}).get("name", "Unknown")

                # Extract priority
                priority_prop = props.get("Priority", {})
                priority = priority_prop.get("select", {}).get("name", "-")

                # Status emoji
                status_emoji = {
                    "Not started": "⚪",
                    "In progress": "🔵",
                    "Done": "✅",
                    "Blocked": "🔴",
                }.get(status, "❓")

                print(f"  {status_emoji} [{priority}] {name}")

    except ValueError as e:
        print(f"❌ 錯誤: {e}")
        return 1

    return 0


def cmd_tasks_create_interactive(args: argparse.Namespace) -> int:
    """Create a task interactively."""
    from notion.tasks import TaskDefinition, TaskPriority, TaskType  # noqa: PLC0415

    project = ProjectInfo.auto_detect()

    print("=" * 60)
    print(f"➕ 建立任務 - {project.name}")
    print("=" * 60)

    # Get task details
    name = input("任務名稱: ").strip()
    if not name:
        print("❌ 任務名稱不能為空")
        return 1

    summary = input("摘要 (可選): ").strip()

    print("\n優先級: 1=High, 2=Medium, 3=Low")
    priority_input = input("選擇 [2]: ").strip() or "2"
    priority_map = {"1": TaskPriority.HIGH, "2": TaskPriority.MEDIUM, "3": TaskPriority.LOW}
    priority = priority_map.get(priority_input, TaskPriority.MEDIUM)

    print("\n類型: 1=Feature, 2=Bug, 3=Setup, 4=Test, 5=Docs")
    type_input = input("選擇 [1]: ").strip() or "1"
    type_map = {
        "1": TaskType.FEATURE,
        "2": TaskType.BUG,
        "3": TaskType.SETUP,
        "4": TaskType.TEST,
        "5": TaskType.DOCS,
    }
    task_type = type_map.get(type_input, TaskType.FEATURE)

    hours_input = input("\n預估時數 [1]: ").strip() or "1"
    try:
        estimated_hours = float(hours_input)
    except ValueError:
        estimated_hours = 1.0

    # Create task
    task = TaskDefinition(
        name=name,
        summary=summary,
        priority=priority,
        task_type=task_type,
        estimated_hours=estimated_hours,
    )

    try:
        with NotionClient() as client:
            pm = ProjectManager(client)
            project_id, _ = pm.get_or_create_project(project)

            tm = TaskManager(client, pm)
            result = tm.create_task(task, project_id)

            print(f"\n✅ 任務已建立!")
            print(f"   ID: {result['id']}")

    except ValueError as e:
        print(f"\n❌ 錯誤: {e}")
        return 1

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Notion 專案整合工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用指令")

    # Project commands
    project_parser = subparsers.add_parser("project", help="專案管理")
    project_sub = project_parser.add_subparsers(dest="subcommand")

    project_sub.add_parser("info", help="顯示當前專案資訊")

    project_create = project_sub.add_parser("create", help="建立/取得專案")
    project_create.add_argument("-d", "--description", help="專案描述")

    # Task commands
    tasks_parser = subparsers.add_parser("tasks", help="任務管理")
    tasks_sub = tasks_parser.add_subparsers(dest="subcommand")

    tasks_sub.add_parser("list", help="列出任務")
    tasks_sub.add_parser("create", help="互動式建立任務")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Route to handlers
    if args.command == "project":
        if args.subcommand == "info":
            return cmd_project_info(args)
        elif args.subcommand == "create":
            return cmd_project_create(args)
        else:
            project_parser.print_help()
            return 0

    elif args.command == "tasks":
        if args.subcommand == "list":
            return cmd_tasks_list(args)
        elif args.subcommand == "create":
            return cmd_tasks_create_interactive(args)
        else:
            tasks_parser.print_help()
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
