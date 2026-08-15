"""Logging setup: stdout + backend/data/server.log (rotating, 10MB × 5 backups)."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import SERVER_LOG_PATH, ensure_dirs

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    ensure_dirs()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(fmt)
    root.addHandler(stdout_handler)

    file_handler = RotatingFileHandler(SERVER_LOG_PATH, maxBytes=10 * 1024 * 1024,
                                       backupCount=5, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # quiet noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    _configured = True
