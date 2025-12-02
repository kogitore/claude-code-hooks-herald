#!/usr/bin/env python3
"""Task management for Notion projects."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .client import NotionClient
from .project import ProjectManager


class TaskPriority(str, Enum):
    """Task priority levels."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TaskStatus(str, Enum):
    """Task status values."""

    NOT_STARTED = "Not started"
    IN_PROGRESS = "In progress"
    DONE = "Done"
    BLOCKED = "Blocked"


class TaskType(str, Enum):
    """Task type categories."""

    FEATURE = "Feature"
    BUG = "Bug"
    SETUP = "Setup"
    TEST = "Test"
    DOCS = "Docs"
    DEPLOY = "Deploy"
    REFACTOR = "Refactor"


class ExecutionMode(str, Enum):
    """Task execution mode."""

    MANUAL = "Manual (人工)"
    AI_ASSISTED = "AI-Assisted (AI 輔助)"
    AUTOMATED = "Automated (自動化)"


@dataclass
class TaskDefinition:
    """Definition of a task to be created."""

    name: str
    summary: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    story_points: str = "1"
    estimated_hours: float = 1.0
    task_type: TaskType = TaskType.FEATURE
    acceptance_criteria: str = ""
    execution_mode: ExecutionMode = ExecutionMode.MANUAL
    blocked_by: list[str] = field(default_factory=list)
    critical_path: bool = False
    start_date: str | None = None

    def to_notion_properties(self, project_id: str) -> dict[str, object]:
        """Convert to Notion page properties.

        Args:
            project_id: The project's Notion ID for relation.

        Returns:
            Properties dict for Notion API.
        """
        properties: dict[str, object] = {
            "Task name": {
                "title": [{"text": {"content": self.name}}],
            },
            "Status": {
                "status": {"name": TaskStatus.NOT_STARTED.value},
            },
            "Priority": {
                "select": {"name": self.priority.value},
            },
            "Story Points": {
                "select": {"name": self.story_points},
            },
            "Estimated Hours": {
                "number": self.estimated_hours,
            },
            "Task Type": {
                "select": {"name": self.task_type.value},
            },
            "Project": {
                "relation": [{"id": project_id}],
            },
        }

        if self.summary:
            properties["Summary"] = {
                "rich_text": [{"text": {"content": self.summary}}],
            }

        if self.acceptance_criteria:
            properties["Acceptance Criteria"] = {
                "rich_text": [{"text": {"content": self.acceptance_criteria}}],
            }

        return properties


@dataclass
class TaskBatchResult:
    """Result of a batch task operation."""

    created: list[tuple[str, str]] = field(default_factory=list)  # (name, id)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (name, error)
    updated: list[tuple[str, str]] = field(default_factory=list)  # (name, id)

    @property
    def success_count(self) -> int:
        return len(self.created) + len(self.updated)

    @property
    def failure_count(self) -> int:
        return len(self.failed)


class TaskManager:
    """Manage tasks in Notion with project association."""

    def __init__(
        self,
        client: NotionClient,
        project_manager: ProjectManager | None = None,
    ) -> None:
        """Initialize the task manager.

        Args:
            client: NotionClient instance.
            project_manager: Optional ProjectManager. Created if not provided.
        """
        self.client = client
        self.project_manager = project_manager or ProjectManager(client)
        self._task_cache: dict[str, str] = {}  # name -> notion_id

    def _ensure_task_db(self) -> str:
        """Ensure task database ID is configured.

        Returns:
            Task database ID.

        Raises:
            ValueError: If NOTION_TASK_DATABASE_ID is not set.
        """
        if not self.client.config.task_db_id:
            raise ValueError("NOTION_TASK_DATABASE_ID is required")
        return self.client.config.task_db_id

    def get_project_tasks(self, project_id: str) -> list[dict[str, object]]:
        """Get all tasks for a project.

        Args:
            project_id: The project's Notion ID.

        Returns:
            List of task page objects.
        """
        return self.client.query_database(
            self._ensure_task_db(),
            filter_={
                "property": "Project",
                "relation": {"contains": project_id},
            },
        )

    def build_task_map(self, project_id: str) -> dict[str, str]:
        """Build a mapping of task names to IDs for a project.

        Args:
            project_id: The project's Notion ID.

        Returns:
            Dict mapping task names to Notion IDs.
        """
        tasks = self.get_project_tasks(project_id)
        task_map: dict[str, str] = {}

        for task in tasks:
            name = self.client.extract_title(task, "Task name")
            if name:
                task_map[name] = task["id"]

        self._task_cache.update(task_map)
        return task_map

    def create_task(
        self,
        task: TaskDefinition,
        project_id: str | None = None,
    ) -> dict[str, object]:
        """Create a single task.

        Args:
            task: Task definition.
            project_id: Optional project ID. Auto-detects if not provided.

        Returns:
            Created task page object.
        """
        if project_id is None:
            _, project_id = self.project_manager.get_current_project()

        properties = task.to_notion_properties(project_id)

        result = self.client.create_page(
            self._ensure_task_db(),
            properties,
        )

        self._task_cache[task.name] = result["id"]
        return result

    def create_tasks_batch(
        self,
        tasks: list[TaskDefinition],
        project_id: str | None = None,
    ) -> TaskBatchResult:
        """Create multiple tasks in batch.

        Args:
            tasks: List of task definitions.
            project_id: Optional project ID. Auto-detects if not provided.

        Returns:
            TaskBatchResult with success/failure details.
        """
        if project_id is None:
            _, project_id = self.project_manager.get_current_project()

        result = TaskBatchResult()

        for task in tasks:
            try:
                page = self.create_task(task, project_id)
                result.created.append((task.name, page["id"]))
            except Exception as e:
                result.failed.append((task.name, str(e)))

        return result

    def update_task_dependencies(
        self,
        dependencies: dict[str, list[str]],
        project_id: str | None = None,
    ) -> TaskBatchResult:
        """Update task dependencies (Block relations).

        Args:
            dependencies: Mapping of task name to list of blocking task names.
            project_id: Optional project ID. Auto-detects if not provided.

        Returns:
            TaskBatchResult with update details.
        """
        if project_id is None:
            _, project_id = self.project_manager.get_current_project()

        # Build task map if not cached
        task_map = self._task_cache or self.build_task_map(project_id)

        result = TaskBatchResult()

        for task_name, blockers in dependencies.items():
            if task_name not in task_map:
                result.failed.append((task_name, "Task not found"))
                continue

            task_id = task_map[task_name]

            # Resolve blocker IDs
            blocker_ids = []
            for blocker_name in blockers:
                if blocker_name in task_map:
                    blocker_ids.append({"id": task_map[blocker_name]})
                else:
                    result.failed.append((task_name, f"Blocker not found: {blocker_name}"))

            if not blocker_ids:
                continue

            try:
                self.client.update_page(
                    task_id,
                    {"Block": {"relation": blocker_ids}},
                )
                result.updated.append((task_name, task_id))
            except Exception as e:
                result.failed.append((task_name, str(e)))

        return result

    def update_task_metadata(
        self,
        task_updates: dict[str, dict[str, object]],
        project_id: str | None = None,
    ) -> TaskBatchResult:
        """Update multiple task properties.

        Args:
            task_updates: Mapping of task name to properties to update.
                Supported keys: execution_mode, start_date, critical_path.
            project_id: Optional project ID. Auto-detects if not provided.

        Returns:
            TaskBatchResult with update details.
        """
        if project_id is None:
            _, project_id = self.project_manager.get_current_project()

        task_map = self._task_cache or self.build_task_map(project_id)
        result = TaskBatchResult()

        for task_name, updates in task_updates.items():
            if task_name not in task_map:
                result.failed.append((task_name, "Task not found"))
                continue

            task_id = task_map[task_name]
            properties: dict[str, object] = {}

            if "execution_mode" in updates:
                mode = updates["execution_mode"]
                if isinstance(mode, ExecutionMode):
                    mode = mode.value
                properties["Execution Mode"] = {"select": {"name": mode}}

            if "start_date" in updates:
                properties["Start Date"] = {"date": {"start": updates["start_date"]}}

            if "critical_path" in updates:
                properties["Critical Path"] = {"checkbox": updates["critical_path"]}

            if not properties:
                continue

            try:
                self.client.update_page(task_id, properties)
                result.updated.append((task_name, task_id))
            except Exception as e:
                result.failed.append((task_name, str(e)))

        return result
