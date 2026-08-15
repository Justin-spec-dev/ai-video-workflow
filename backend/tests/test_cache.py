"""test_cache.py: hash 稳定性（坐标变化不改变 hash）、输入变化改变 hash (SPEC §11)."""
from app.workflow.cache import compute_cache_key


def test_position_change_does_not_change_hash():
    # 坐标在 node.position，不参与 cache hash —— 两个只有坐标不同的节点 hash 相同
    node_a = {"id": "n1", "type": "prompt", "position": {"x": 0, "y": 0},
              "config": {"text": "hello"}}
    node_b = {"id": "n1", "type": "prompt", "position": {"x": 500, "y": 300},
              "config": {"text": "hello"}}
    inputs = {}
    h1 = compute_cache_key(node_a["type"], "1.0.0", node_a["config"], inputs)
    h2 = compute_cache_key(node_b["type"], "1.0.0", node_b["config"], inputs)
    assert h1 == h2


def test_config_change_changes_hash():
    h1 = compute_cache_key("prompt", "1.0.0", {"text": "a"}, {})
    h2 = compute_cache_key("prompt", "1.0.0", {"text": "b"}, {})
    assert h1 != h2


def test_input_change_changes_hash():
    config = {"text": "x"}
    h1 = compute_cache_key("prompt_optimizer", "1.0.0", config, {"prompt": "cat"})
    h2 = compute_cache_key("prompt_optimizer", "1.0.0", config, {"prompt": "dog"})
    assert h1 != h2


def test_hash_stable_across_calls():
    config = {"b": 2, "a": 1}
    inputs = {"prompt": "hello", "extra": [1, 2, {"k": "v"}]}
    assert compute_cache_key("llm", "1.0.0", config, inputs) == \
        compute_cache_key("llm", "1.0.0", {"a": 1, "b": 2}, inputs)


def test_ui_fields_stripped():
    h1 = compute_cache_key("prompt", "1.0.0", {"text": "a"}, {})
    h2 = compute_cache_key("prompt", "1.0.0", {"text": "a", "_selected": True}, {})
    assert h1 == h2


def test_media_input_ignores_run_timestamped_path(tmp_path):
    """回归：outputs 路径含 run_<ts> 时间戳，旧实现（key 嵌入绝对路径）导致
    媒体下游节点缓存永远 miss。同一文件内容未变 → key 必须稳定。"""
    import os
    import shutil

    a = tmp_path / "run_1" / "nodes" / "n1" / "video.mp4"
    a.parent.mkdir(parents=True)
    a.write_bytes(b"FAKE-MP4-CONTENT")
    # 模拟 run_2 目录里"内容相同"的文件（copy2 保留 mtime，指纹一致）
    b = tmp_path / "run_2" / "nodes" / "n1" / "video.mp4"
    b.parent.mkdir(parents=True)
    shutil.copy2(a, b)
    assert a.stat().st_mtime_ns == b.stat().st_mtime_ns  # 指纹前提

    media_a = {"path": str(a), "url": "/api/files/outputs/run_1/nodes/n1/video.mp4", "filename": "video.mp4"}
    media_b = {"path": str(b), "url": "/api/files/outputs/run_2/nodes/n1/video.mp4", "filename": "video.mp4"}
    h1 = compute_cache_key("last_frame", "1.0.0", {}, {"video": media_a})
    h2 = compute_cache_key("last_frame", "1.0.0", {}, {"video": media_b})
    assert h1 == h2


def test_media_content_change_changes_hash(tmp_path):
    """同一路径文件内容变化 → 指纹变化 → key 变化（缓存正确失效）。"""
    f = tmp_path / "frame.png"
    f.write_bytes(b"AAA")
    h1 = compute_cache_key("video_generation", "1.0.0", {"model": "m"}, {"image": {"path": str(f)}})
    f.write_bytes(b"BBB")
    h2 = compute_cache_key("video_generation", "1.0.0", {"model": "m"}, {"image": {"path": str(f)}})
    assert h1 != h2


def test_missing_media_file_keeps_path_in_key(tmp_path):
    """文件不存在时（异常输出/外部引用）退回原行为，且两次 key 一致（确定性）。"""
    path = str(tmp_path / "nonexistent.png")
    h1 = compute_cache_key("video_generation", "1.0.0", {}, {"image": {"path": path}})
    h2 = compute_cache_key("video_generation", "1.0.0", {}, {"image": {"path": path}})
    assert h1 == h2
