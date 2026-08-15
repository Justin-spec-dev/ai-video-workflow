"""Application configuration and path constants."""
from __future__ import annotations

import os
from pathlib import Path

# backend/ directory
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
# ai-video-workflow/ project root
ROOT_DIR = BACKEND_DIR.parent

DATA_DIR = BACKEND_DIR / "data"
OUTPUTS_DIR = BACKEND_DIR / "outputs"
TEMP_DIR = BACKEND_DIR / "temp"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"
SECRET_KEY_PATH = DATA_DIR / ".secret_key"
SERVER_LOG_PATH = DATA_DIR / "server.log"

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "2"))

# 每个工作流保留的最近 run 输出目录数，超出部分在下次运行时清理（含引用它们的缓存条目）
OUTPUT_RETENTION = int(os.environ.get("OUTPUT_RETENTION", "20"))

# FFmpeg lookup order: env FFMPEG_PATH -> project tools/ffmpeg -> system PATH
PROJECT_FFMPEG_DIR = ROOT_DIR / "tools" / "ffmpeg"


def ensure_dirs() -> None:
    for d in (DATA_DIR, OUTPUTS_DIR, TEMP_DIR, UPLOADS_DIR):
        d.mkdir(parents=True, exist_ok=True)
