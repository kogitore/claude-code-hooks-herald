import unittest
import os
import json
import sys
from pathlib import Path
from unittest.mock import patch, mock_open

# Ensure the hooks directory is importable when this file is executed as a script
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_ROOT = REPO_ROOT / ".claude" / "hooks"
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from utils.config_manager import ConfigManager

class TestConfigManager(unittest.TestCase):

    def setUp(self):
        """Set up for each test."""
        # Reset the singleton instance before each test to ensure isolation
        ConfigManager._instance = None
        ConfigManager._initialized = False
        self.temp_dir = "temp_test_config_dir"
        os.makedirs(self.temp_dir, exist_ok=True)
        
        self.config1_path = os.path.join(self.temp_dir, "config1.json")
        self.config1_data = {"key1": "value1", "nested": {"key2": "value2"}}
        with open(self.config1_path, 'w') as f:
            json.dump(self.config1_data, f)

    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.config1_path):
            os.remove(self.config1_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
        ConfigManager._instance = None
        ConfigManager._initialized = False

    def test_singleton_instance(self):
        """Test that ConfigManager is a singleton."""
        instance1 = ConfigManager.get_instance()
        instance2 = ConfigManager.get_instance()
        self.assertIs(instance1, instance2)

    def test_initialization(self):
        """Test the initialization of the ConfigManager."""
        search_paths = [self.temp_dir]
        manager = ConfigManager.get_instance(search_paths=search_paths)
        self.assertEqual(manager.search_paths, search_paths)

    def test_load_config_success(self):
        """Test successful loading of a config file."""
        manager = ConfigManager.get_instance(search_paths=[self.temp_dir])
        config = manager.load_config("config1.json")
        self.assertEqual(config, self.config1_data)

    def test_load_config_not_found(self):
        """Test loading a non-existent config file."""
        manager = ConfigManager.get_instance(search_paths=[self.temp_dir])
        config = manager.load_config("non_existent_config.json")
        self.assertEqual(config, {})

    def test_load_config_invalid_json(self):
        """Test loading a file with invalid JSON content."""
        invalid_json_path = os.path.join(self.temp_dir, "invalid.json")
        with open(invalid_json_path, 'w') as f:
            f.write("{'key': 'value'}") # Invalid JSON
        
        manager = ConfigManager.get_instance(search_paths=[self.temp_dir])
        config = manager.load_config("invalid.json")
        self.assertEqual(config, {})
        
        os.remove(invalid_json_path)

    def test_config_caching(self):
        """Test that configuration is cached after the first load."""
        manager = ConfigManager.get_instance(search_paths=[self.temp_dir])
        
        # Mock open to trace file access
        m = mock_open(read_data=json.dumps(self.config1_data))
        with patch('builtins.open', m):
            # First call, should read the file
            config1 = manager.get_config("config1.json")
            m.assert_called_once_with(os.path.join(self.temp_dir, "config1.json"), 'r')
            
            # Second call, should use cache and not read the file again
            m.reset_mock()
            config2 = manager.get_config("config1.json")
            m.assert_not_called()
            
            self.assertEqual(config1, self.config1_data)
            self.assertIs(config1, config2) # Should be the same object from cache

    def test_get_from_config(self):
        """Test getting a specific value from a config file."""
        manager = ConfigManager.get_instance(search_paths=[self.temp_dir])
        
        # Test getting an existing key
        value = manager.get_from_config("config1.json", "key1")
        self.assertEqual(value, "value1")
        
        # Test getting a nested key (requires dot notation support or manual traversal)
        nested_value = manager.get_from_config("config1.json", "nested")
        self.assertEqual(nested_value, {"key2": "value2"})
        
        # Test getting a non-existent key with a default value
        default_value = manager.get_from_config("config1.json", "non_existent_key", "default")
        self.assertEqual(default_value, "default")
        
        # Test getting from a non-existent file
        value_from_none = manager.get_from_config("non_existent.json", "key", "default")
        self.assertEqual(value_from_none, "default")

    def test_clear_cache(self):
        """Test clearing the cache."""
        manager = ConfigManager.get_instance(search_paths=[self.temp_dir])
        manager.load_config("config1.json")
        self.assertIn("config1.json", manager._config_cache)
        
        manager.clear_cache()
        self.assertNotIn("config1.json", manager._config_cache)

if __name__ == '__main__':
    unittest.main()
