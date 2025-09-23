#!/usr/bin/env python3
"""Smoke tests for utils.constants module."""
from __future__ import annotations

import sys
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))


def test_constants_importable() -> None:
    from utils import constants  # noqa: F401


if __name__ == "__main__":  # pragma: no cover
    import unittest

    unittest.main()
