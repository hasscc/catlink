"""Pytest configuration and fixtures for CatLink tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add repo root to path so custom_components.catlink can be imported
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest_plugins = ("pytest_homeassistant_custom_component",)
