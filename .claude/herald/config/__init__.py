"""Herald configuration files."""
from __future__ import annotations

from pathlib import Path

CONFIG_DIR = Path(__file__).parent

AUDIO_CONFIG_PATH = CONFIG_DIR / "audio_config.json"
DECISION_POLICY_PATH = CONFIG_DIR / "decision_policy.json"

__all__ = [
    "CONFIG_DIR",
    "AUDIO_CONFIG_PATH",
    "DECISION_POLICY_PATH",
]
