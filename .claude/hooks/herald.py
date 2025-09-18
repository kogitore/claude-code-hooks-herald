#!/usr/bin/env python3
"""
Claude Code Hooks Herald - Central Event Dispatcher

This module provides the central dispatcher for all Claude Code hook events.
It implements the middleware chain pattern and routes events to appropriate handlers.
"""

import json
import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from abc import ABC, abstractmethod

from .utils.audio_manager import AudioManager


class HeraldDispatcher:
    """Central event dispatcher for Claude Code hooks."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the dispatcher with configuration."""
        self.config_path = config_path or Path(".claude/settings.json")
        self.event_handlers: Dict[str, Any] = {}
        self.middleware_chain: List[Any] = []
        self.audio_manager = AudioManager()
        self.logger = self._setup_logging()

        # Load configuration
        self.config = self._load_config()

        # Initialize event mapping
        self._initialize_event_handlers()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the dispatcher."""
        logger = logging.getLogger("herald")
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

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from settings.json."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                self.logger.warning(f"Config file not found: {self.config_path}")
                return {}
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}

    def _initialize_event_handlers(self):
        """Initialize the mapping of events to handlers."""
        # This will be populated as we migrate existing hooks
        self.event_handlers = {
            "notification": None,  # Will map to notification.py
            "stop": None,          # Will map to stop.py
            "subagent_stop": None, # Will map to subagent_stop.py
            # Future events to be implemented
            "pre_tool_use": None,
            "post_tool_use": None,
            "session_start": None,
            "user_prompt_submit": None,
            "tool_execution_start": None,
            "tool_execution_end": None,
        }

    def dispatch(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch an event through the middleware chain and to appropriate handler.

        Args:
            event_type: The type of event (e.g., 'notification', 'pre_tool_use')
            payload: The event payload data

        Returns:
            Dict containing the response from the handler
        """
        start_time = time.time()

        try:
            # 1. Run through middleware chain
            processed_payload = self._run_middleware(event_type, payload)

            # 2. Route to appropriate handler
            handler = self.event_handlers.get(event_type)
            if not handler:
                self.logger.warning(f"No handler found for event: {event_type}")
                return {"status": "no_handler", "event_type": event_type}

            # 3. Execute handler
            result = handler.process(processed_payload)

            # 4. Play audio if configured
            self._handle_audio(event_type, result)

            # 5. Log the event
            duration_ms = (time.time() - start_time) * 1000
            self._log_event(event_type, payload, result, duration_ms)

            return result

        except Exception as e:
            self.logger.error(f"Error dispatching event {event_type}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "event_type": event_type
            }

    def _run_middleware(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run the payload through the middleware chain."""
        processed_payload = payload.copy()

        for middleware in self.middleware_chain:
            try:
                processed_payload = middleware.process(event_type, processed_payload)
            except Exception as e:
                self.logger.error(f"Middleware error: {e}")
                # Continue with original payload if middleware fails
                break

        return processed_payload

    def _handle_audio(self, event_type: str, result: Dict[str, Any]):
        """Handle audio playback based on event type and result."""
        if not self.config.get("audio", {}).get("enabled", True):
            return

        # Default audio mapping - will be made configurable
        audio_map = {
            "notification": "user_prompt.wav",
            "stop": "task_complete.wav",
            "subagent_stop": "agent_complete.wav",
            "tool_execution_start": "user_prompt.wav",
            "tool_execution_end": "success.wav",
        }

        audio_file = audio_map.get(event_type)
        if audio_file and result.get("status") != "error":
            try:
                self.audio_manager.play_sound(audio_file)
            except Exception as e:
                self.logger.error(f"Audio playback failed: {e}")

    def _log_event(self, event_type: str, payload: Dict[str, Any],
                   result: Dict[str, Any], duration_ms: float):
        """Log the event for observability."""
        log_entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "duration_ms": round(duration_ms, 2),
            "status": result.get("status", "unknown"),
            "payload_size": len(str(payload)),
        }

        # Log to structured logger (can be extended to JSONL file)
        self.logger.info(f"Event processed: {json.dumps(log_entry)}")

    def register_handler(self, event_type: str, handler):
        """Register a handler for a specific event type."""
        self.event_handlers[event_type] = handler
        self.logger.info(f"Registered handler for {event_type}")

    def add_middleware(self, middleware):
        """Add middleware to the processing chain."""
        self.middleware_chain.append(middleware)
        self.logger.info(f"Added middleware: {middleware.__class__.__name__}")


def main():
    """Main entry point for testing the dispatcher."""
    dispatcher = HeraldDispatcher()

    # Test event
    test_event = {
        "message": "Test notification",
        "timestamp": time.time()
    }

    result = dispatcher.dispatch("notification", test_event)
    print(f"Dispatch result: {result}")


if __name__ == "__main__":
    main()