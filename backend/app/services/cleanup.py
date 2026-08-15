"""Run-output retention (optimization: outputs/<slug>/run_* 无限堆积).

Keeps only the newest N run directories per workflow. Deleted directories are referenced by
CacheEntry / NodeRun rows (their outputs JSON embeds per-run absolute paths), so those rows are
removed first — otherwise the cache would point at deleted files and downstream nodes would
re-fail with FileNotFoundError on cache hits.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy import delete

from ..models.orm import CacheEntry, NodeRun

logger = logging.getLogger("workflow.cleanup")

DEFAULT_KEEP_RUNS = 20


async def cleanup_old_outputs(session_factory, slug_dir: Path, keep: int = DEFAULT_KEEP_RUNS) -> int:
    """Delete the oldest run_* directories beyond `keep`; returns how many were removed.

    CacheEntry / NodeRun rows whose outputs reference a removed run directory are deleted in the
    same pass (cache 命中后读不到文件 = FAILED，所以必须同步清掉相关缓存)。
    """
    if keep < 1 or not slug_dir.is_dir():
        return 0
    runs = sorted(
        (p for p in slug_dir.iterdir() if p.is_dir() and p.name.startswith("run_")),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    removed = 0
    for old in runs[keep:]:
        marker = old.name  # run_<ts>_<id6>，出现在 outputs JSON 的绝对路径中
        try:
            async with session_factory() as session:
                for model in (CacheEntry, NodeRun):
                    await session.execute(delete(model).where(model.outputs.like(f"%{marker}%")))
                await session.commit()
            shutil.rmtree(old, ignore_errors=True)
            removed += 1
        except Exception:  # 清理失败不影响本次运行
            logger.exception("清理 run 目录失败: %s", old)
    if removed:
        logger.info("清理 %d 个旧 run 目录（%s 保留最近 %d 个）", removed, slug_dir.name, keep)
    return removed
