"""Workflow execution engine (SPEC §5.5): topo-layer parallel execution, caching,
failure propagation, cancel / resume / run_from_here, paid-run confirmation flow."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..core.config import MAX_CONCURRENCY, OUTPUTS_DIR
from ..core.database import SessionLocal
from ..core.events import bus
from ..core.security import redact
from ..credentials.service import CredentialService
from ..models.orm import CacheEntry, NodeRun, Task, Workflow, WorkflowRun, utcnow_iso
from ..nodes.base import NODE_REGISTRY
from ..services import ffmpeg as ffmpeg_service
from ..services.settings import get_settings
from . import dag
from .cache import compute_cache_key
from .context import ExecutionContext, NodeCancelledError, ServiceRegistry, slugify

logger = logging.getLogger("workflow.engine")


class RunLimitError(Exception):
    """409 — run policy limits exceeded."""


@dataclass
class RunHandle:
    run_id: str
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None


class WorkflowEngine:
    def __init__(self, session_factory: async_sessionmaker = SessionLocal):
        self.session_factory = session_factory
        self.active: dict[str, RunHandle] = {}

    # ------------------------------------------------------------------ run creation

    async def create_run(self, workflow_id: str, *, trigger: str = "manual",
                         confirm_paid: bool = False, resume_from_run_id: str | None = None,
                         run_from_node_id: str | None = None, downstream: bool = True) -> dict:
        from ..services.cost import estimate_workflow  # local import to avoid cycle

        async with self.session_factory() as session:
            wf = await session.get(Workflow, workflow_id)
            if wf is None:
                raise ValueError(f"Workflow 不存在: {workflow_id}")
            data = json.loads(wf.data or "{}")
            nodes = data.get("nodes", [])
            if not nodes:
                raise ValueError("Workflow 没有节点")
            dag.validate(nodes, data.get("edges", []))

            settings = await get_settings(session)
            price = ((settings.get("pricing") or {}).get("minimax") or {}).get("per_second")
            estimate = estimate_workflow(data, price_per_second=price)

            paid_count = estimate["paid_node_count"]
            if paid_count > 0:
                max_paid = settings.get("max_paid_tasks_per_run")
                if max_paid is not None and paid_count > max_paid:
                    raise RunLimitError(
                        f"付费节点数 {paid_count} 超过单次运行上限 max_paid_tasks_per_run={max_paid}")
                max_cost = settings.get("max_estimated_cost_per_run")
                if max_cost is not None and estimate.get("estimated_cost") is not None \
                        and estimate["estimated_cost"] > max_cost:
                    raise RunLimitError(
                        f"预估费用 {estimate['estimated_cost']} 超过上限 max_estimated_cost_per_run={max_cost}")

            waiting = paid_count > 0 and settings.get("require_confirmation", True) and not confirm_paid
            run = WorkflowRun(
                workflow_id=workflow_id,
                status="waiting_confirmation" if waiting else "running",
                trigger=trigger,
                cost_estimate=json.dumps(estimate, ensure_ascii=False),
            )
            session.add(run)
            await session.commit()
            run_id = run.id

        if waiting:
            bus.publish("workflow.cost", {"run_id": run_id, "estimate": estimate})
            return {"run_id": run_id, "status": "waiting_confirmation", "estimate": estimate}

        self._schedule(run_id, resume_from_run_id=resume_from_run_id,
                       run_from_node_id=run_from_node_id, downstream=downstream)
        return {"run_id": run_id, "status": "running", "estimate": estimate}

    async def confirm(self, run_id: str) -> dict:
        async with self.session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if run is None:
                raise ValueError(f"Run 不存在: {run_id}")
            if run.status != "waiting_confirmation":
                raise ValueError(f"Run 状态为 {run.status}，无法 confirm")
            run.status = "running"
            await session.commit()
        self._schedule(run_id)
        return {"run_id": run_id, "status": "running"}

    async def stop(self, run_id: str) -> dict:
        handle = self.active.get(run_id)
        if handle is not None:
            handle.cancel_event.set()
            return {"run_id": run_id, "status": "cancelling"}
        async with self.session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if run is None:
                raise ValueError(f"Run 不存在: {run_id}")
            if run.status in ("running", "waiting_confirmation"):
                run.status = "cancelled"
                run.finished_at = utcnow_iso()
                await session.commit()
        return {"run_id": run_id, "status": "cancelled"}

    def _schedule(self, run_id: str, **kwargs) -> None:
        handle = RunHandle(run_id=run_id)
        self.active[run_id] = handle
        handle.task = asyncio.create_task(self._execute(run_id, handle, **kwargs))

    # ------------------------------------------------------------------ execution

    async def _execute(self, run_id: str, handle: RunHandle, *,
                       resume_from_run_id: str | None = None,
                       run_from_node_id: str | None = None,
                       downstream: bool = True) -> None:
        try:
            await self.execute(run_id, handle.cancel_event,
                               resume_from_run_id=resume_from_run_id,
                               run_from_node_id=run_from_node_id, downstream=downstream)
        except Exception:
            logger.exception("run %s 执行异常", run_id)
            async with self.session_factory() as session:
                run = await session.get(WorkflowRun, run_id)
                if run is not None and run.status == "running":
                    run.status = "failed"
                    run.error = "引擎内部错误（见 server.log）"
                    run.finished_at = utcnow_iso()
                    await session.commit()
            bus.publish("workflow.finished", {"run_id": run_id, "status": "failed"})
        finally:
            self.active.pop(run_id, None)

    async def execute(self, run_id: str, cancel_event: asyncio.Event | None = None, *,
                      resume_from_run_id: str | None = None,
                      run_from_node_id: str | None = None,
                      downstream: bool = True) -> str:
        """Run to completion; returns final status. Usable synchronously from tests."""
        cancel_event = cancel_event or asyncio.Event()
        async with self.session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            wf = await session.get(Workflow, run.workflow_id)
            workflow_id = wf.id
            data = json.loads(wf.data or "{}")
            wf_name = wf.name

        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        node_by_id = {n["id"]: n for n in nodes}
        layers = dag.topo_layers(nodes, edges)

        out_dir = OUTPUTS_DIR / slugify(wf_name) / f"run_{int(time.time())}_{run_id[:6]}"
        out_dir.mkdir(parents=True, exist_ok=True)

        services = ServiceRegistry(
            ffmpeg=ffmpeg_service,
            credentials=_SessionedCredentialService(self.session_factory),
            session_factory=self.session_factory,
        )

        context = ExecutionContext(
            workflow_id=workflow_id, run_id=run_id,
            output_dir=out_dir, cancel_event=cancel_event, services=services,
        )

        # ---- reuse outputs from previous runs (resume / run_from_here upstream) ----
        reused: dict[str, str] = {}  # node_id -> reused-from status
        if resume_from_run_id:
            async with self.session_factory() as session:
                q = select(NodeRun).where(
                    NodeRun.run_id == resume_from_run_id,
                    NodeRun.status.in_(("SUCCESS", "CACHED")))
                for nr in (await session.execute(q)).scalars():
                    if nr.outputs:
                        context.node_results[nr.node_id] = json.loads(nr.outputs)
                        reused[nr.node_id] = nr.status
        elif run_from_node_id:
            rerun = {run_from_node_id}
            if downstream:
                rerun |= dag.descendants(nodes, edges, run_from_node_id)
            context.force_rerun = rerun
            for nid in node_by_id:
                if nid in rerun:
                    continue
                outputs = await self._latest_successful_outputs(workflow_id, nid)
                if outputs is not None:
                    context.node_results[nid] = outputs
                    reused[nid] = "SUCCESS"

        bus.publish("workflow.started", {"run_id": run_id, "workflow_id": workflow_id})
        await context.log(f"Run 开始（trigger 复用 {len(reused)} 个节点结果）")

        # record reused nodes as CACHED node_runs in this run
        for nid, status in reused.items():
            n = node_by_id.get(nid)
            await self._record_node_run(session_factory=self.session_factory, run_id=run_id,
                                        workflow_id=workflow_id, node_id=nid,
                                        node_type=n["type"] if n else "?",
                                        status="CACHED", outputs=context.node_results[nid])
            context.node_statuses[nid] = "CACHED"
            bus.publish("node.cached", {"run_id": run_id, "node_id": nid,
                                        "node_type": n["type"] if n else "?",
                                        "outputs": context.node_results[nid]})

        # ---- topo-layer parallel execution ----
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        rev = dag.reverse_graph(nodes, edges)
        any_failed = False

        # ---- variables pre-pass ----
        # 变量注入型节点（无输入）先于层循环执行，确保同层 prompt 节点的
        # {{var}} 模板能确定性解析（否则执行顺序是竞争态）。
        for n in nodes:
            cls = NODE_REGISTRY.get(n["type"])
            if getattr(cls, "provides_variables", False) and n["id"] not in context.node_statuses:
                status = await self._run_node(context, n, edges, rev, semaphore)
                if status == "FAILED":
                    any_failed = True

        for layer in layers:
            if cancel_event.is_set():
                for nid in layer:
                    if nid not in context.node_statuses:
                        context.node_statuses[nid] = "CANCELLED"
                        bus.publish("node.cancelled", {"run_id": run_id, "node_id": nid,
                                                       "node_type": node_by_id[nid]["type"]})
                continue
            to_run = [nid for nid in layer if nid not in context.node_statuses]
            results = await asyncio.gather(*(
                self._run_node(context, node_by_id[nid], edges, rev, semaphore)
                for nid in to_run
            ))
            for status in results:
                if status == "FAILED":
                    any_failed = True

        # ---- final status ----
        if any_failed:
            final = "failed"
        elif cancel_event.is_set():
            final = "cancelled"
        else:
            final = "success"
        async with self.session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            run.status = final
            run.finished_at = utcnow_iso()
            if any_failed:
                failed = [nid for nid, s in context.node_statuses.items() if s == "FAILED"]
                run.error = f"失败节点: {', '.join(failed)}"
            await session.commit()
        bus.publish("workflow.finished", {"run_id": run_id, "status": final})
        await context.log(f"Run 结束: {final}")
        return final

    async def _latest_successful_outputs(self, workflow_id: str, node_id: str) -> dict | None:
        async with self.session_factory() as session:
            q = (select(NodeRun)
                 .where(NodeRun.workflow_id == workflow_id, NodeRun.node_id == node_id,
                        NodeRun.status.in_(("SUCCESS", "CACHED")))
                 .order_by(NodeRun.started_at.desc()))
            nr = (await session.execute(q)).scalars().first()
            return json.loads(nr.outputs) if nr and nr.outputs else None

    # ------------------------------------------------------------------ single node

    def _resolve_inputs(self, node: dict, edges: list[dict],
                        context: ExecutionContext) -> dict:
        cls = NODE_REGISTRY.get(node["type"])
        inputs: dict = {}
        for port in cls.inputs:
            incoming = [e for e in edges
                        if e["target"] == node["id"] and e.get("target_handle") == port.key]
            if port.multiple:
                values = [context.node_results[e["source"]].get(e["source_handle"])
                          for e in incoming if e["source"] in context.node_results]
                if values:
                    inputs[port.key] = values
            else:
                for e in incoming:
                    if e["source"] in context.node_results:
                        inputs[port.key] = context.node_results[e["source"]].get(e["source_handle"])
                        break
        return inputs

    async def _run_node(self, context: ExecutionContext, node: dict, edges: list[dict],
                        rev: dict[str, list[str]], semaphore: asyncio.Semaphore) -> str:
        run_id, nid, ntype = context.run_id, node["id"], node["type"]
        wf_id = context.workflow_id

        # failure propagation: upstream failed/cancelled -> skip as CANCELLED
        upstream_failed = [up for up in rev.get(nid, [])
                           if context.node_statuses.get(up) in ("FAILED", "CANCELLED")]
        if upstream_failed:
            context.node_statuses[nid] = "CANCELLED"
            await self._record_node_run(session_factory=self.session_factory, run_id=run_id,
                                        workflow_id=wf_id, node_id=nid, node_type=ntype,
                                        status="CANCELLED",
                                        error=f"上游节点失败/取消: {', '.join(upstream_failed)}")
            bus.publish("node.cancelled", {"run_id": run_id, "node_id": nid, "node_type": ntype})
            await context.log(f"因上游 {upstream_failed} 失败而跳过", level="warning", node_id=nid)
            return "CANCELLED"

        bus.publish("node.queued", {"run_id": run_id, "node_id": nid, "node_type": ntype})
        async with semaphore:
            if context.cancel_event.is_set():
                context.node_statuses[nid] = "CANCELLED"
                bus.publish("node.cancelled", {"run_id": run_id, "node_id": nid, "node_type": ntype})
                return "CANCELLED"

            cls = NODE_REGISTRY.get(ntype)
            config = node.get("config") or {}
            inputs = self._resolve_inputs(node, edges, context)
            cache_key = compute_cache_key(ntype, cls.version, config, inputs)

            # cache lookup（run_from_here 的目标节点强制重跑，绕过缓存）
            cached = None if nid in context.force_rerun else await self._cache_lookup(wf_id, nid, cache_key)
            if cached is not None:
                context.node_statuses[nid] = "CACHED"
                context.node_results[nid] = cached
                await self._record_node_run(session_factory=self.session_factory, run_id=run_id,
                                            workflow_id=wf_id, node_id=nid, node_type=ntype,
                                            status="CACHED", inputs=inputs, outputs=cached,
                                            cache_key=cache_key, config=config)
                bus.publish("node.cached", {"run_id": run_id, "node_id": nid,
                                            "node_type": ntype, "outputs": cached})
                await context.log("命中缓存，复用 outputs", node_id=nid)
                return "CACHED"

            bus.publish("node.running", {"run_id": run_id, "node_id": nid, "node_type": ntype})
            started = utcnow_iso()
            context.current_node_id = nid
            try:
                instance = cls()
                outputs = await instance.execute(inputs, config, context)
                context.node_statuses[nid] = "SUCCESS"
                context.node_results[nid] = outputs
                remote_task_id = await self._node_remote_task_id(run_id, nid)
                await self._cache_store(wf_id, nid, cache_key, outputs)
                await self._record_node_run(session_factory=self.session_factory, run_id=run_id,
                                            workflow_id=wf_id, node_id=nid, node_type=ntype,
                                            status="SUCCESS", inputs=inputs, outputs=outputs,
                                            cache_key=cache_key, config=config, task_id=remote_task_id,
                                            started_at=started, finished_at=utcnow_iso())
                bus.publish("node.success", {"run_id": run_id, "node_id": nid,
                                             "node_type": ntype, "outputs": outputs})
                return "SUCCESS"
            except NodeCancelledError:
                context.node_statuses[nid] = "CANCELLED"
                await self._record_node_run(session_factory=self.session_factory, run_id=run_id,
                                            workflow_id=wf_id, node_id=nid, node_type=ntype,
                                            status="CANCELLED", inputs=inputs,
                                            cache_key=cache_key, config=config,
                                            started_at=started, finished_at=utcnow_iso(),
                                            error="已取消")
                bus.publish("node.cancelled", {"run_id": run_id, "node_id": nid, "node_type": ntype})
                return "CANCELLED"
            except Exception as e:  # noqa: BLE001 — node failures must not kill the engine
                err = redact(str(e) or repr(e))
                context.node_statuses[nid] = "FAILED"
                remote_task_id = await self._node_remote_task_id(run_id, nid)
                await self._record_node_run(session_factory=self.session_factory, run_id=run_id,
                                            workflow_id=wf_id, node_id=nid, node_type=ntype,
                                            status="FAILED", inputs=inputs,
                                            cache_key=cache_key, config=config, task_id=remote_task_id,
                                            started_at=started, finished_at=utcnow_iso(),
                                            error=err)
                bus.publish("node.failed", {"run_id": run_id, "node_id": nid,
                                            "node_type": ntype, "error": err})
                await context.log(f"节点执行失败: {err}", level="error", node_id=nid)
                return "FAILED"

    # ------------------------------------------------------------------ persistence

    async def _cache_lookup(self, workflow_id: str, node_id: str, cache_key: str) -> dict | None:
        async with self.session_factory() as session:
            q = select(CacheEntry).where(CacheEntry.workflow_id == workflow_id,
                                         CacheEntry.node_id == node_id,
                                         CacheEntry.cache_key == cache_key)
            entry = (await session.execute(q)).scalars().first()
            return json.loads(entry.outputs) if entry else None

    async def _cache_store(self, workflow_id: str, node_id: str, cache_key: str, outputs: dict) -> None:
        async with self.session_factory() as session:
            session.add(CacheEntry(workflow_id=workflow_id, node_id=node_id,
                                   cache_key=cache_key,
                                   outputs=json.dumps(outputs, ensure_ascii=False, default=str)))
            try:
                await session.commit()
            except Exception:  # unique race between parallel runs — harmless
                await session.rollback()

    async def clear_cache(self, workflow_id: str, node_id: str) -> int:
        from sqlalchemy import delete
        async with self.session_factory() as session:
            result = await session.execute(
                delete(CacheEntry).where(CacheEntry.workflow_id == workflow_id,
                                         CacheEntry.node_id == node_id))
            await session.commit()
            return result.rowcount or 0

    async def _node_remote_task_id(self, run_id: str, node_id: str) -> str | None:
        """节点关联的最新一条 provider task 的 remote_task_id（用于 node_runs 回溯）。"""
        async with self.session_factory() as session:
            q = (select(Task).where(Task.run_id == run_id, Task.node_id == node_id)
                 .order_by(Task.created_at.desc()))
            t = (await session.execute(q)).scalars().first()
            return t.remote_task_id if t else None

    async def _record_node_run(self, *, session_factory, run_id, workflow_id, node_id,
                               node_type, status, inputs=None, outputs=None, cache_key=None,
                               config=None, error=None, started_at=None, finished_at=None,
                               task_id=None) -> None:
        config = config or {}
        async with session_factory() as session:
            nr = NodeRun(
                run_id=run_id, workflow_id=workflow_id, node_id=node_id, node_type=node_type,
                status=status,
                inputs=json.dumps(inputs, ensure_ascii=False, default=str) if inputs is not None else None,
                outputs=json.dumps(outputs, ensure_ascii=False, default=str) if outputs is not None else None,
                cache_key=cache_key,
                provider=config.get("provider"),
                model=config.get("model"),
                credential_id=config.get("credential_id"),
                task_id=task_id,
                error=error, started_at=started_at, finished_at=finished_at,
            )
            session.add(nr)
            await session.commit()


class _SessionedCredentialService:
    """CredentialService wrapper that opens a fresh session per call (safe across tasks)."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def resolve(self, credential_id, *, kind, provider=None):
        async with self.session_factory() as session:
            return await CredentialService(session).resolve(credential_id, kind=kind, provider=provider)


# shared engine instance used by the API layer
engine = WorkflowEngine()
