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
