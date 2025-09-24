import json
import os
from threading import Lock
from typing import Any, Dict, Optional, List

class ConfigManager:
    _instance: Optional["ConfigManager"] = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.search_paths: List[str] = []
        self._config_cache: Dict[str, Any] = {}
        self._file_lock = Lock()
        self._initialized = True

    def _find_config_file(self, file_name: str) -> Optional[str]:
        """Finds a config file in the search paths."""
        for path in self.search_paths:
            full_path = os.path.join(path, file_name)
            if os.path.exists(full_path):
                return full_path
        return None

    def load_config(self, file_name: str) -> Dict[str, Any]:
        """
        Loads a JSON configuration file.
        Caches the content to avoid redundant file I/O.
        """
        with self._file_lock:
            if file_name in self._config_cache:
                return self._config_cache[file_name]

            config_path = self._find_config_file(file_name)
            if not config_path:
                # Return empty dict if file not found, to prevent crashes
                self._config_cache[file_name] = {}
                return {}

            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                self._config_cache[file_name] = config
                return config
            except (json.JSONDecodeError, FileNotFoundError):
                # Return empty dict on error
                self._config_cache[file_name] = {}
                return {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Gets a configuration value by searching through loaded configs.
        The search order is reverse of loading. Last loaded is checked first.
        Supports dot notation for nested keys (e.g., 'audio.volume').
        """
        with self._file_lock:
            # Search through all cached configs in reverse order (last loaded first)
            for file_name in reversed(list(self._config_cache.keys())):
                config = self._config_cache[file_name]
                value = self._get_nested_value(config, key)
                if value is not None:
                    return value
            return default

    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """
        Gets a value from nested dictionary using dot notation.
        Returns None if key not found.
        """
        if '.' not in key:
            return config.get(key)
        
        keys = key.split('.')
        current = config
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current

    def get_config(self, file_name: str) -> Dict[str, Any]:
        """
        Returns the full configuration dictionary for a given file.
        Loads it if not already cached.
        """
        return self.load_config(file_name)

    def clear_cache(self):
        """Clears the configuration cache."""
        with self._file_lock:
            self._config_cache.clear()

    @classmethod
    def get_instance(cls, search_paths: Optional[List[str]] = None) -> "ConfigManager":
        """Gets the singleton instance, initializing it if necessary."""
        instance = cls()
        if search_paths is not None:
            instance.search_paths = search_paths
        return instance

    def get_from_config(self, file_name: str, key: str, default: Any = None) -> Any:
        """
        Gets a specific key from a specific configuration file.
        """
        config = self.get_config(file_name)
        return config.get(key, default)
