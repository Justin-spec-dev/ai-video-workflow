"""test_dag.py: topo 排序、环检测、缺输入、类型不兼容 (SPEC §11)."""
import pytest

from app.workflow.dag import (WorkflowValidationError, detect_cycle,
                              topological_sort, validate)


def _n(nid, type_, config=None):
    return {"id": nid, "type": type_, "position": {"x": 0, "y": 0}, "config": config or {}}


def _e(eid, s, sh, t, th):
    return {"id": eid, "source": s, "source_handle": sh, "target": t, "target_handle": th}


def test_topological_sort_chain():
    nodes = [_n("a", "prompt"), _n("b", "prompt_optimizer"), _n("c", "video_generation")]
    edges = [_e("e1", "a", "prompt", "b", "prompt"), _e("e2", "b", "prompt", "c", "prompt")]
    order = topological_sort(nodes, edges)
    assert order.index("a") < order.index("b") < order.index("c")


def test_topological_sort_parallel_branches():
    nodes = [_n("a", "prompt"), _n("b", "text")]
    assert set(topological_sort(nodes, [])) == {"a", "b"}


def test_detect_cycle():
    nodes = [_n("a", "combine_prompt"), _n("b", "combine_prompt")]
    edges = [_e("e1", "a", "prompt", "b", "character"), _e("e2", "b", "prompt", "a", "character")]
    assert detect_cycle(nodes, edges) is True
    with pytest.raises(WorkflowValidationError):
        topological_sort(nodes, edges)


def test_no_cycle():
    nodes = [_n("a", "prompt"), _n("b", "prompt_optimizer")]
    edges = [_e("e1", "a", "prompt", "b", "prompt")]
    assert detect_cycle(nodes, edges) is False


def test_missing_required_input():
    nodes = [_n("a", "llm")]  # llm.prompt is required
    with pytest.raises(WorkflowValidationError, match="缺少必填输入"):
        validate(nodes, [])


def test_type_incompatible():
    nodes = [_n("a", "video_preview"), _n("b", "llm")]
    # VIDEO -> TEXT is forbidden (only PROMPT<->TEXT interchangeable)
    edges = [_e("e1", "a", "video", "b", "prompt")]
    with pytest.raises(WorkflowValidationError, match="端口类型不兼容"):
        validate(nodes, edges)


def test_prompt_text_compatible():
    nodes = [_n("a", "prompt"), _n("b", "llm")]  # PROMPT -> TEXT allowed
    edges = [_e("e1", "a", "prompt", "b", "prompt")]
    validate(nodes, edges)


def test_video_into_video_array_allowed():
    nodes = [_n("a", "video_generation"), _n("p", "prompt"), _n("m", "video_merge")]
    edges = [_e("e0", "p", "prompt", "a", "prompt"), _e("e1", "a", "video", "m", "videos")]
    validate(nodes, edges)


def test_duplicate_single_input_rejected():
    nodes = [_n("a", "prompt"), _n("b", "prompt"), _n("c", "prompt_optimizer")]
    edges = [_e("e1", "a", "prompt", "c", "prompt"), _e("e2", "b", "prompt", "c", "prompt")]
    with pytest.raises(WorkflowValidationError, match="单输入端口"):
        validate(nodes, edges)


def test_unknown_node_type():
    with pytest.raises(WorkflowValidationError, match="未知节点类型"):
        validate([_n("a", "does_not_exist")], [])


def test_unknown_node_id():
    nodes = [_n("a", "prompt")]
    edges = [_e("e1", "a", "prompt", "ghost", "prompt")]
    with pytest.raises(WorkflowValidationError, match="不存在"):
        validate(nodes, edges)
