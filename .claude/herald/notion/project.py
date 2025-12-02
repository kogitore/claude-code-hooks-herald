#!/usr/bin/env python3
"""Project management with automatic folder-based naming."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .client import NotionClient


@dataclass
class ProjectInfo:
    """Project information with auto-detection capabilities."""

    name: str
    root_path: Path
    notion_id: str | None = None
    description: str = ""
    status: str = "Active"
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_folder(cls, folder_path: Path | str | None = None) -> "ProjectInfo":
        """Create ProjectInfo from a folder path.

        The project name is derived from the folder name.

        Args:
            folder_path: Path to project root. If None, uses current working directory.

        Returns:
            ProjectInfo with name set to folder name.
        """
        if folder_path is None:
            folder_path = Path.cwd()
        elif isinstance(folder_path, str):
            folder_path = Path(folder_path)

        folder_path = folder_path.resolve()
        name = folder_path.name

        return cls(
            name=name,
            root_path=folder_path,
        )

    @classmethod
    def auto_detect(cls) -> "ProjectInfo":
        """Auto-detect project from current working directory.

        Walks up the directory tree to find project root indicators:
        - .git directory
        - pyproject.toml
        - package.json
        - .claude directory

        Returns:
            ProjectInfo for the detected project.
        """
        cwd = Path.cwd()
        current = cwd

        # Walk up to find project root
        indicators = [".git", "pyproject.toml", "package.json", ".claude"]

        while current != current.parent:
            for indicator in indicators:
                if (current / indicator).exists():
                    return cls.from_folder(current)
            current = current.parent

        # Fallback to cwd if no indicators found
        return cls.from_folder(cwd)


class ProjectManager:
    """Manage projects in Notion with auto-detection."""

    def __init__(self, client: NotionClient) -> None:
        """Initialize the project manager.

        Args:
            client: NotionClient instance for API calls.
        """
        self.client = client
        self._project_cache: dict[str, str] = {}  # name -> notion_id

    def find_project_by_name(self, name: str) -> dict[str, object] | None:
        """Find a project in Notion by name.

        Args:
            name: Project name to search for.

        Returns:
            Project page object, or None if not found.
        """
        if not self.client.config.project_db_id:
            raise ValueError("NOTION_PROJECT_DATABASE_ID is required")

        results = self.client.query_database(
            self.client.config.project_db_id,
            filter_={
                "property": "Project name",
                "title": {"equals": name},
            },
        )

        return results[0] if results else None

    def get_or_create_project(
        self,
        project_info: ProjectInfo | None = None,
    ) -> tuple[str, bool]:
        """Get existing project or create a new one.

        Args:
            project_info: Project information. If None, auto-detects from folder.

        Returns:
            Tuple of (project_id, was_created).
        """
        if project_info is None:
            project_info = ProjectInfo.auto_detect()

        # Check cache first
        if project_info.name in self._project_cache:
            return self._project_cache[project_info.name], False

        # Search in Notion
        existing = self.find_project_by_name(project_info.name)
        if existing:
            project_id = existing["id"]
            self._project_cache[project_info.name] = project_id
            return project_id, False

        # Create new project
        if not self.client.config.project_db_id:
            raise ValueError("NOTION_PROJECT_DATABASE_ID is required to create projects")

        properties = {
            "Project name": {
                "title": [{"text": {"content": project_info.name}}],
            },
            "Status": {
                "status": {"name": project_info.status},
            },
        }

        # Add optional description
        if project_info.description:
            properties["Description"] = {
                "rich_text": [{"text": {"content": project_info.description}}],
            }

        result = self.client.create_page(
            self.client.config.project_db_id,
            properties,
        )

        project_id = result["id"]
        self._project_cache[project_info.name] = project_id
        return project_id, True

    def list_projects(self, status: str | None = None) -> list[dict[str, object]]:
        """List all projects, optionally filtered by status.

        Args:
            status: Optional status filter (e.g., "Active", "Completed").

        Returns:
            List of project page objects.
        """
        if not self.client.config.project_db_id:
            raise ValueError("NOTION_PROJECT_DATABASE_ID is required")

        filter_ = None
        if status:
            filter_ = {
                "property": "Status",
                "status": {"equals": status},
            }

        return self.client.query_database(
            self.client.config.project_db_id,
            filter_=filter_,
        )

    def get_current_project(self) -> tuple[ProjectInfo, str]:
        """Get current project based on working directory.

        Returns:
            Tuple of (ProjectInfo, project_notion_id).

        Raises:
            ValueError: If project not found and can't be created.
        """
        project_info = ProjectInfo.auto_detect()
        project_id, _ = self.get_or_create_project(project_info)
        project_info.notion_id = project_id
        return project_info, project_id
