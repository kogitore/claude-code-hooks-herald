#!/usr/bin/env python3
"""
Base Hook Framework for Claude Code Hooks Herald

This module provides the abstract base class and common functionality
for all hook implementations in the Herald system.
"""

import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path


class BaseHook(ABC):
    """Abstract base class for all Claude Code hooks."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the base hook.

        Args:
            name: The name of the hook
            config: Optional configuration dictionary
        """
        self.name = name
        self.config = config or {}
        self.logger = self._setup_logging()
        self.performance_threshold_ms = 50  # Maximum execution time

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the hook."""
        logger = logging.getLogger(f"hook.{self.name}")
        logger.setLevel(logging.INFO)

        # Create console handler if not exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    @abstractmethod
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """
        Validate the input data for this hook.

        Args:
            data: The input data to validate

        Returns:
            True if the input is valid, False otherwise
        """
        pass

    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the hook with the given data.

        Args:
            data: The input data to process

        Returns:
            Dictionary containing the result of processing
        """
        pass

    @abstractmethod
    def handle_error(self, error: Exception) -> Dict[str, Any]:
        """
        Handle errors that occur during processing.

        Args:
            error: The exception that occurred

        Returns:
            Dictionary containing error information
        """
        pass

    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the hook with performance monitoring and error handling.

        This is the main entry point that should be called by the dispatcher.

        Args:
            data: The input data to process

        Returns:
            Dictionary containing the execution result
        """
        start_time = time.time()

        try:
            # 1. Validate input
            if not self.validate_input(data):
                return {
                    "status": "validation_error",
                    "error": "Input validation failed",
                    "hook_name": self.name
                }

            # 2. Process the hook
            result = self.process(data)

            # 3. Check performance
            duration_ms = (time.time() - start_time) * 1000
            if duration_ms > self.performance_threshold_ms:
                self.logger.warning(
                    f"Hook {self.name} exceeded performance threshold: "
                    f"{duration_ms:.2f}ms > {self.performance_threshold_ms}ms"
                )

            # 4. Add metadata to result
            if isinstance(result, dict):
                result.update({
                    "hook_name": self.name,
                    "duration_ms": round(duration_ms, 2),
                    "timestamp": time.time()
                })

            return result

        except Exception as e:
            self.logger.error(f"Error in hook {self.name}: {e}")
            return self.handle_error(e)

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value with fallback.

        Args:
            key: The configuration key
            default: Default value if key is not found

        Returns:
            The configuration value or default
        """
        return self.config.get(key, default)

    def is_enabled(self) -> bool:
        """
        Check if this hook is enabled.

        Returns:
            True if the hook is enabled, False otherwise
        """
        return self.get_config_value("enabled", True)


class NotificationHook(BaseHook):
    """Hook for handling notification events."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("notification", config)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate notification input."""
        # Notification hooks can accept any data
        return isinstance(data, dict)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process notification event."""
        self.logger.info(f"Processing notification: {data.get('message', 'No message')}")

        return {
            "status": "success",
            "action": "notification_processed",
            "message": data.get("message", ""),
            "audio_requested": True
        }

    def handle_error(self, error: Exception) -> Dict[str, Any]:
        """Handle notification errors."""
        return {
            "status": "error",
            "error": str(error),
            "hook_name": self.name,
            "audio_requested": False
        }


class StopHook(BaseHook):
    """Hook for handling stop events."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("stop", config)
        self.stop_count = 0
        self.max_stops = 3  # Prevent infinite loops

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate stop input."""
        return isinstance(data, dict) and "transcript" in data

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process stop event."""
        self.stop_count += 1

        # Check for infinite loop prevention
        if self.stop_count > self.max_stops:
            self.logger.warning(f"Stop hook called {self.stop_count} times, preventing infinite loop")
            return {
                "status": "blocked",
                "reason": f"Maximum stop count ({self.max_stops}) exceeded",
                "decision": "block"
            }

        transcript = data.get("transcript", {})

        # Simple completion check
        if self._needs_completion(transcript):
            return {
                "status": "continue",
                "decision": "continue",
                "reason": "Task appears incomplete"
            }

        return {
            "status": "success",
            "decision": "allow",
            "reason": "Task completed successfully",
            "audio_requested": True
        }

    def _needs_completion(self, transcript: Dict[str, Any]) -> bool:
        """Check if the task needs completion."""
        # Simple heuristic - can be enhanced
        content = str(transcript).lower()
        incomplete_indicators = [
            "todo",
            "fixme",
            "error",
            "failed",
            "incomplete"
        ]

        return any(indicator in content for indicator in incomplete_indicators)

    def handle_error(self, error: Exception) -> Dict[str, Any]:
        """Handle stop errors."""
        return {
            "status": "error",
            "error": str(error),
            "hook_name": self.name,
            "decision": "allow"  # Safe default
        }


def main():
    """Test the base hook framework."""
    # Test notification hook
    notification_hook = NotificationHook()
    test_data = {"message": "Test notification"}
    result = notification_hook.execute(test_data)
    print(f"Notification result: {result}")

    # Test stop hook
    stop_hook = StopHook()
    test_data = {"transcript": {"content": "Task completed successfully"}}
    result = stop_hook.execute(test_data)
    print(f"Stop result: {result}")


if __name__ == "__main__":
    main()