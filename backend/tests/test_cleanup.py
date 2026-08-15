"""test_cleanup.py: outputs 保留策略 —— 只删最老的 run 目录，且同步清掉引用它们的
缓存/历史行（否则缓存命中后读不到文件 = FAILED）。"""
import os

from sqlalchemy import select

from app.models.orm import CacheEntry, NodeRun
from app.services.cleanup import cleanup_old_outputs


def _make_run_dir(base, name):
    d = base / name
    d.mkdir(parents=True)
    (d / "video.mp4").write_bytes(b"x")
    return d


async def test_cleanup_removes_oldest_runs_and_referencing_rows(session_factory, tmp_path):
    slug = tmp_path / "wf-slug"
    r1 = _make_run_dir(slug, "run_111")
    r2 = _make_run_dir(slug, "run_222")
    r3 = _make_run_dir(slug, "run_333")
    # 确定性排序：按 mtime 从新到旧 = run_333 > run_222 > run_111
    os.utime(r1, (1, 1))
    os.utime(r2, (2, 2))
    os.utime(r3, (3, 3))

    async with session_factory() as s:
        s.add_all([
            CacheEntry(workflow_id="w1", node_id="lf", cache_key="k-old",
                       outputs='{"video": {"path": "%s"}}' % (r1 / "video.mp4")),
            CacheEntry(workflow_id="w1", node_id="lf", cache_key="k-new",
                       outputs='{"video": {"path": "%s"}}' % (r3 / "video.mp4")),
            NodeRun(run_id="r-old", workflow_id="w1", node_id="lf", node_type="last_frame",
                    status="SUCCESS",
                    outputs='{"image": {"path": "%s"}}' % (r1 / "video.mp4")),
            NodeRun(run_id="r-other", workflow_id="w1", node_id="other", node_type="prompt",
                    status="SUCCESS", outputs=None),
        ])
        await s.commit()

    removed = await cleanup_old_outputs(session_factory, slug, keep=1)
    assert removed == 2
    assert not r1.exists() and not r2.exists()
    assert r3.exists()

    async with session_factory() as s:
        caches = (await s.execute(select(CacheEntry))).scalars().all()
        runs = (await s.execute(select(NodeRun))).scalars().all()
    assert [c.cache_key for c in caches] == ["k-new"]      # 引用已删目录的缓存被清掉
    assert [r.node_id for r in runs] == ["other"]           # 历史行同步清理，未引用者保留


async def test_cleanup_keep_all_when_under_limit(session_factory, tmp_path):
    slug = tmp_path / "wf-slug"
    _make_run_dir(slug, "run_111")
    _make_run_dir(slug, "run_222")
    removed = await cleanup_old_outputs(session_factory, slug, keep=5)
    assert removed == 0
    assert (slug / "run_111").exists() and (slug / "run_222").exists()


async def test_cleanup_missing_dir_is_noop(session_factory, tmp_path):
    assert await cleanup_old_outputs(session_factory, tmp_path / "nope", keep=1) == 0
