"""Workflow 数据安全网（防止误删/异常覆盖导致的工作流丢失）。

- 每次创建/保存，在 ``data/backups/<id>.json`` 保留最新一份完整备份；
- 删除前把完整 JSON 移入 ``data/trash/<时间戳>_<id>.json``，可手动恢复。
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from ..core.config import DATA_DIR

logger = logging.getLogger("services.backup")

BACKUPS_DIR = DATA_DIR / "backups"
TRASH_DIR = DATA_DIR / "trash"


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_ " else "_" for c in (name or ""))[:40].strip() or "unnamed"


def _dump(directory: Path, filename: str, wf_id: str, name: str, data: str) -> None:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": wf_id,
            "name": name,
            "data": json.loads(data or "{}"),
            "backed_up_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        (directory / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # 备份失败绝不能影响主流程
        logger.exception("workflow 备份失败: %s", wf_id)


def backup_workflow(wf_id: str, name: str, data: str) -> None:
    """每次保存后调用：保留该工作流最新一份完整快照。"""
    _dump(BACKUPS_DIR, f"{wf_id}.json", wf_id, name, data)


def trash_workflow(wf_id: str, name: str, data: str) -> None:
    """删除前调用：完整 JSON 进回收站（带时间戳，同 id 可多次删除互不覆盖）。"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    _dump(TRASH_DIR, f"{ts}_{_safe_name(name)}_{wf_id}.json", wf_id, name, data)
