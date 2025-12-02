#!/usr/bin/env python3
"""Notion API client with automatic project detection."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv


@dataclass
class NotionConfig:
    """Configuration for Notion API connection."""

    token: str
    project_db_id: str | None = None
    task_db_id: str | None = None
    api_version: str = "2022-06-28"

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "NotionConfig":
        """Load configuration from environment variables.

        Args:
            env_path: Optional path to .env file. If None, searches up the directory tree.
        """
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        token = os.getenv("NOTION_API_TOKEN")
        if not token:
            raise ValueError("NOTION_API_TOKEN is required")

        return cls(
            token=token,
            project_db_id=os.getenv("NOTION_PROJECT_DATABASE_ID"),
            task_db_id=os.getenv("NOTION_TASK_DATABASE_ID"),
        )


class NotionClient:
    """Generic Notion API client with project auto-detection."""

    BASE_URL = "https://api.notion.com/v1"

    def __init__(self, config: NotionConfig | None = None) -> None:
        """Initialize the Notion client.

        Args:
            config: Optional configuration. If None, loads from environment.
        """
        self.config = config or NotionConfig.from_env()
        self._client: httpx.Client | None = None

    @property
    def headers(self) -> dict[str, str]:
        """HTTP headers for Notion API requests."""
        return {
            "Authorization": f"Bearer {self.config.token}",
            "Notion-Version": self.config.api_version,
            "Content-Type": "application/json",
        }

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialized HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "NotionClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # =========================================================================
    # Database Operations
    # =========================================================================

    def query_database(
        self,
        database_id: str,
        filter_: dict[str, object] | None = None,
        sorts: list[dict[str, object]] | None = None,
        page_size: int = 100,
    ) -> list[dict[str, object]]:
        """Query a Notion database.

        Args:
            database_id: The database ID to query.
            filter_: Optional filter object.
            sorts: Optional sort specifications.
            page_size: Number of results per page (max 100).

        Returns:
            List of page objects from the database.
        """
        payload: dict[str, object] = {"page_size": page_size}
        if filter_:
            payload["filter"] = filter_
        if sorts:
            payload["sorts"] = sorts

        response = self.client.post(
            f"{self.BASE_URL}/databases/{database_id}/query",
            headers=self.headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json().get("results", [])

    # =========================================================================
    # Page Operations
    # =========================================================================

    def create_page(
        self,
        database_id: str,
        properties: dict[str, object],
    ) -> dict[str, object]:
        """Create a new page in a database.

        Args:
            database_id: Target database ID.
            properties: Page properties.

        Returns:
            Created page object.
        """
        payload = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }

        response = self.client.post(
            f"{self.BASE_URL}/pages",
            headers=self.headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def update_page(
        self,
        page_id: str,
        properties: dict[str, object],
    ) -> dict[str, object]:
        """Update a page's properties.

        Args:
            page_id: The page ID to update.
            properties: Properties to update.

        Returns:
            Updated page object.
        """
        response = self.client.patch(
            f"{self.BASE_URL}/pages/{page_id}",
            headers=self.headers,
            json={"properties": properties},
        )
        response.raise_for_status()
        return response.json()

    def get_page(self, page_id: str) -> dict[str, object]:
        """Retrieve a page by ID.

        Args:
            page_id: The page ID to retrieve.

        Returns:
            Page object.
        """
        response = self.client.get(
            f"{self.BASE_URL}/pages/{page_id}",
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def extract_title(page: dict[str, object], property_name: str = "Name") -> str:
        """Extract title text from a page property.

        Args:
            page: Page object from Notion API.
            property_name: Name of the title property.

        Returns:
            Plain text title, or empty string if not found.
        """
        props = page.get("properties", {})
        title_prop = props.get(property_name, {})
        title_array = title_prop.get("title", [])
        if title_array:
            return title_array[0].get("plain_text", "")
        return ""

    @staticmethod
    def extract_rich_text(page: dict[str, object], property_name: str) -> str:
        """Extract rich text content from a page property.

        Args:
            page: Page object from Notion API.
            property_name: Name of the rich_text property.

        Returns:
            Plain text content, or empty string if not found.
        """
        props = page.get("properties", {})
        rt_prop = props.get(property_name, {})
        rt_array = rt_prop.get("rich_text", [])
        if rt_array:
            return rt_array[0].get("plain_text", "")
        return ""
