"""test_engine.py: 并行执行、失败传播、cancel、cache 命中（CACHED）、run_from_here (SPEC §11)."""
import asyncio
import json
import time

import pytest
from sqlalchemy import select

from app.nodes.base import BaseNode, ConfigField, PortDef, register_node
from app.workflow.context import NodeExecutionError
from app.workflow.engine import WorkflowEngine
from app.models.orm import NodeRun, WorkflowRun

from conftest import make_workflow

EXEC_COUNT: dict[str, int] = {}


def _count(context):
    nid = context.current_node_id
    EXEC_COUNT[nid] = EXEC_COUNT.get(nid, 0) + 1


@register_node
class FakeSourceNode(BaseNode):
    type = "fake_source"
    name = "Fake Source"
    category = "Text"
    outputs = [PortDef(key="text", name="Text", type="TEXT")]
    config_schema = [ConfigField(key="value", name="Value", type="text", default="")]

    async def execute(self, inputs, config, context):
        _count(context)
        return {"text": config.get("value", "")}


@register_node
class FakeEchoNode(BaseNode):
    type = "fake_echo"
    name = "Fake Echo"
    category = "Text"
    inputs = [PortDef(key="text", name="Text", type="TEXT", required=True)]
    outputs = [PortDef(key="text", name="Text", type="TEXT")]

    async def execute(self, inputs, config, context):
        _count(context)
        return {"text": inputs.get("text")}


@register_node
class FakeFailNode(BaseNode):
    type = "fake_fail"
    name = "Fake Fail"
    category = "Text"
    inputs = [PortDef(key="text", name="Text", type="TEXT", required=False)]
    outputs = [PortDef(key="text", name="Text", type="TEXT")]

    async def execute(self, inputs, config, context):
        _count(context)
        raise NodeExecutionError("boom")


@register_node
class FakeSlowNode(BaseNode):
    type = "fake_slow"
    name = "Fake Slow"
    category = "Text"
    outputs = [PortDef(key="text", name="Text", type="TEXT")]

    async def execute(self, inputs, config, context):
        _count(context)
        for _ in range(200):
            context.check_cancelled()
            await asyncio.sleep(0.05)
        return {"text": "done"}


@register_node
class FakeSleepyNode(BaseNode):
    type = "fake_sleepy"
    name = "Fake Sleepy"
    category = "Text"
    outputs = [PortDef(key="text", name="Text", type="TEXT")]

    async def execute(self, inputs, config, context):
        await asyncio.sleep(0.4)
        return {"text": "ok"}


def _n(nid, type_, config=None):
    return {"id": nid, "type": type_, "position": {"x": 0, "y": 0}, "config": config or {}}


def _e(eid, s, sh, t, th):
    return {"id": eid, "source": s, "source_handle": sh, "target": t, "target_handle": th}


@pytest.fixture
def eng(session_factory, monkeypatch, tmp_path):
    import app.workflow.engine as engine_mod
    monkeypatch.setattr(engine_mod, "OUTPUTS_DIR", tmp_path / "outputs")
    EXEC_COUNT.clear()
    return WorkflowEngine(session_factory=session_factory)


async def _run_to_completion(eng: WorkflowEngine, wf_id: str, **kwargs) -> str:
    result = await eng.create_run(wf_id, confirm_paid=True, **kwargs)
    run_id = result["run_id"]
    task = eng.active[run_id].task
    await task
    return run_id


async def _statuses(session_factory, run_id) -> dict[str, str]:
    async with session_factory() as s:
        rows = (await s.execute(select(NodeRun).where(NodeRun.run_id == run_id))).scalars()
        return {nr.node_id: nr.status for nr in rows}


async def _run_status(session_factory, run_id) -> str:
    async with session_factory() as s:
        return (await s.get(WorkflowRun, run_id)).status


async def test_parallel_execution_and_success(eng, session_factory):
    data = {"version": 1, "nodes": [_n("s1", "fake_sleepy"), _n("s2", "fake_sleepy")], "edges": []}
    wf_id = await make_workflow(session_factory, data)
    start = time.monotonic()
    run_id = await _run_to_completion(eng, wf_id)
    elapsed = time.monotonic() - start
    assert await _run_status(session_factory, run_id) == "success"
    statuses = await _statuses(session_factory, run_id)
    assert statuses == {"s1": "SUCCESS", "s2": "SUCCESS"}
    # 串行需 ~0.8s；并行（Semaphore=2）应明显更快
    assert elapsed < 0.75


async def test_failure_propagation(eng, session_factory):
    # f 失败 → 下游 d 标 CANCELLED；独立分支 i 继续 SUCCESS
    data = {"version": 1, "nodes": [
        _n("f", "fake_fail"),
        _n("d", "fake_echo"),
        _n("i", "fake_source", {"value": "independent"}),
    ], "edges": [_e("e1", "f", "text", "d", "text")]}
    wf_id = await make_workflow(session_factory, data)
    run_id = await _run_to_completion(eng, wf_id)
    assert await _run_status(session_factory, run_id) == "failed"
    statuses = await _statuses(session_factory, run_id)
    assert statuses["f"] == "FAILED"
    assert statuses["d"] == "CANCELLED"
    assert statuses["i"] == "SUCCESS"


async def test_cancel(eng, session_factory):
    data = {"version": 1, "nodes": [_n("slow", "fake_slow")], "edges": []}
    wf_id = await make_workflow(session_factory, data)
    result = await eng.create_run(wf_id, confirm_paid=True)
    run_id = result["run_id"]
    task = eng.active[run_id].task
    await asyncio.sleep(0.3)
    await eng.stop(run_id)
    await task
    assert await _run_status(session_factory, run_id) == "cancelled"
    statuses = await _statuses(session_factory, run_id)
    assert statuses["slow"] == "CANCELLED"


async def test_cache_hit_second_run(eng, session_factory):
    data = {"version": 1, "nodes": [
        _n("a", "fake_source", {"value": "v"}),
        _n("b", "fake_echo"),
    ], "edges": [_e("e1", "a", "text", "b", "text")]}
    wf_id = await make_workflow(session_factory, data)
    run1 = await _run_to_completion(eng, wf_id)
    assert (await _statuses(session_factory, run1)) == {"a": "SUCCESS", "b": "SUCCESS"}
    assert EXEC_COUNT == {"a": 1, "b": 1}

    run2 = await _run_to_completion(eng, wf_id)
    statuses2 = await _statuses(session_factory, run2)
    assert statuses2 == {"a": "CACHED", "b": "CACHED"}
    assert EXEC_COUNT == {"a": 1, "b": 1}  # 没有重新执行

    # 修改 config 后 hash 变化 → 重新执行
    async with session_factory() as s:
        from app.models.orm import Workflow
        wf = await s.get(Workflow, wf_id)
        d = json.loads(wf.data)
        d["nodes"][0]["config"]["value"] = "changed"
        wf.data = json.dumps(d, ensure_ascii=False)
        await s.commit()
    run3 = await _run_to_completion(eng, wf_id)
    statuses3 = await _statuses(session_factory, run3)
    assert statuses3["a"] == "SUCCESS"
    # b 的输入来自 a 的 output，上游变化 → b 也重新执行
    assert statuses3["b"] == "SUCCESS"


async def test_run_from_here(eng, session_factory):
    data = {"version": 1, "nodes": [
        _n("a", "fake_source", {"value": "v"}),
        _n("b", "fake_echo"),
        _n("c", "fake_echo"),
    ], "edges": [_e("e1", "a", "text", "b", "text"), _e("e2", "b", "text", "c", "text")]}
    wf_id = await make_workflow(session_factory, data)
    run1 = await _run_to_completion(eng, wf_id)
    assert EXEC_COUNT == {"a": 1, "b": 1, "c": 1}

    run2 = await _run_to_completion(eng, wf_id, trigger="run_from_here", run_from_node_id="b")
    statuses2 = await _statuses(session_factory, run2)
    assert statuses2["a"] == "CACHED"      # 上游复用
    assert statuses2["b"] == "SUCCESS"
    assert statuses2["c"] == "SUCCESS"
    assert EXEC_COUNT == {"a": 1, "b": 2, "c": 2}  # a 未重新执行


async def test_resume(eng, session_factory):
    data = {"version": 1, "nodes": [
        _n("ok", "fake_source", {"value": "v"}),
        _n("bad", "fake_fail"),
    ], "edges": []}
    wf_id = await make_workflow(session_factory, data)
    run1 = await _run_to_completion(eng, wf_id)
    assert await _run_status(session_factory, run1) == "failed"
    assert EXEC_COUNT == {"ok": 1, "bad": 1}

    run2 = await _run_to_completion(eng, wf_id, trigger="resume", resume_from_run_id=run1)
    statuses2 = await _statuses(session_factory, run2)
    assert statuses2["ok"] == "CACHED"   # 旧 run SUCCESS 复用
    assert statuses2["bad"] == "FAILED"  # 重跑仍失败
    assert EXEC_COUNT == {"ok": 1, "bad": 2}
