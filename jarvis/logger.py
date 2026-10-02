"""Central logging setup for Jarvis."""
from __future__ import annotations

import json
import logging
import os

_LOGGER_INITIALIZED = False


def _load_level() -> str:
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(base, "config", "settings.json")
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        return str(settings.get("logging", {}).get("level", "INFO")).upper()
    except Exception:
        return "INFO"


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger (idempotent basicConfig)."""
    global _LOGGER_INITIALIZED
    if not _LOGGER_INITIALIZED:
        level = getattr(logging, _load_level(), logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        _LOGGER_INITIALIZED = True
    return logging.getLogger(name)
