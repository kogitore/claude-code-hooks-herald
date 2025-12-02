"""Notion integration module for Claude Code projects.

This module provides a generic Notion integration that automatically
adapts to different projects based on the folder name.
"""
from __future__ import annotations

from .client import NotionClient
from .project import ProjectManager
from .tasks import TaskManager

__all__ = ["NotionClient", "ProjectManager", "TaskManager"]
