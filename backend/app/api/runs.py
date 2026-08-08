"""Runs API (SPEC §6)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..models.orm import NodeRun, WorkflowRun
from ..workflow.engine import RunLimitError, engine
from ..workflow.dag import WorkflowValidationError

router = APIRouter(prefix="/runs", tags=["runs"])


def _run_dict(run: WorkflowRun, *, with_nodes: bool = False, node_runs=None) -> dict:
    d = {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "trigger": run.trigger,
        "cost_estimate": json.loads(run.cost_estimate) if run.cost_estimate else None,
        "error": run.error,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }
    if with_nodes:
        d["node_runs"] = [{
            "id": nr.id, "node_id": nr.node_id, "node_type": nr.node_type,
            "status": nr.status,
            "inputs": json.loads(nr.inputs) if nr.inputs else None,
            "outputs": json.loads(nr.outputs) if nr.outputs else None,
            "cache_key": nr.cache_key, "provider": nr.provider, "model": nr.model,
            "credential_id": nr.credential_id, "task_id": nr.task_id, "error": nr.error,
            "started_at": nr.started_at, "finished_at": nr.finished_at,
        } for nr in (node_runs or [])]
    return d


@router.get("")
async def list_runs(workflow_id: str | None = None, session: AsyncSession = Depends(get_session)):
    q = select(WorkflowRun).order_by(WorkflowRun.started_at.desc())
    if workflow_id:
        q = q.where(WorkflowRun.workflow_id == workflow_id)
    rows = (await session.execute(q)).scalars()
    return [_run_dict(r) for r in rows]


@router.get("/{run_id}")
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(404, "Run 不存在")
    nrs = (await session.execute(
        select(NodeRun).where(NodeRun.run_id == run_id).order_by(NodeRun.started_at)
    )).scalars()
    return _run_dict(run, with_nodes=True, node_runs=nrs)


@router.post("/{run_id}/confirm")
async def confirm_run(run_id: str):
    try:
        return await engine.confirm(run_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{run_id}/stop")
async def stop_run(run_id: str):
    try:
        return await engine.stop(run_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{run_id}/resume")
async def resume_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(404, "Run 不存在")
    try:
        return await engine.create_run(
            run.workflow_id, trigger="resume", confirm_paid=True, resume_from_run_id=run_id,
        )
    except RunLimitError as e:
        raise HTTPException(409, str(e))
    except WorkflowValidationError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
