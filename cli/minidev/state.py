from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .system import home_dir

MINIDEV_HOME = ".minidev"
CONFIG_FILE = "config.json"
MANIFEST_FILE = "manifest.json"


def minidev_dir() -> Path:
    return home_dir() / MINIDEV_HOME


def config_path() -> Path:
    return minidev_dir() / CONFIG_FILE


def manifest_path() -> Path:
    return minidev_dir() / MANIFEST_FILE


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
