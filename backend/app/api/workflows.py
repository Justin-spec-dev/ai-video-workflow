"""Workflow CRUD + estimate + run + per-node actions (SPEC §6)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..models.orm import Workflow
from ..models.schemas import (NodeRunRequest, RunRequest, WorkflowCreate,
                              WorkflowUpdate, assert_no_secrets)
from ..services.backup import backup_workflow, trash_workflow
from ..services.cost import estimate_workflow
from ..services.settings import get_settings
from ..workflow.dag import WorkflowValidationError, validate
from ..workflow.engine import RunLimitError, engine

router = APIRouter(prefix="/workflows", tags=["workflows"])

_DEFAULT_DATA = {"version": 1, "nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}


def _wf_dict(wf: Workflow, *, with_data: bool = True) -> dict:
    d = {"id": wf.id, "name": wf.name, "updated_at": wf.updated_at}
    if with_data:
        d["data"] = json.loads(wf.data or "{}")
        d["created_at"] = wf.created_at
    return d


@router.get("")
async def list_workflows(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Workflow).order_by(Workflow.updated_at.desc()))).scalars()
    return [_wf_dict(w, with_data=False) for w in rows]


@router.post("", status_code=201)
async def create_workflow(body: WorkflowCreate, session: AsyncSession = Depends(get_session)):
    data = body.data or _DEFAULT_DATA
    try:
        assert_no_secrets(data)
        if data.get("nodes"):
            validate(data["nodes"], data.get("edges", []))
    except (ValueError, WorkflowValidationError) as e:
        raise HTTPException(400, str(e))
    wf = Workflow(name=body.name, data=json.dumps(data, ensure_ascii=False))
    session.add(wf)
    await session.commit()
    backup_workflow(wf.id, wf.name, wf.data)
    return _wf_dict(wf)


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, session: AsyncSession = Depends(get_session)):
    wf = await session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow 不存在")
    return _wf_dict(wf)


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, body: WorkflowUpdate,
                          session: AsyncSession = Depends(get_session)):
    wf = await session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow 不存在")
    if body.name is not None:
        wf.name = body.name
    if body.data is not None:
        try:
            assert_no_secrets(body.data)
            if body.data.get("nodes"):
                validate(body.data["nodes"], body.data.get("edges", []))
        except (ValueError, WorkflowValidationError) as e:
            raise HTTPException(400, str(e))
        wf.data = json.dumps(body.data, ensure_ascii=False)
    await session.commit()
    backup_workflow(wf.id, wf.name, wf.data)
    return _wf_dict(wf)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, session: AsyncSession = Depends(get_session)):
    wf = await session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow 不存在")
    trash_workflow(wf.id, wf.name, wf.data or "{}")
    await session.delete(wf)
    await session.commit()


@router.post("/{workflow_id}/duplicate", status_code=201)
async def duplicate_workflow(workflow_id: str, session: AsyncSession = Depends(get_session)):
    wf = await session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow 不存在")
    clone = Workflow(name=f"{wf.name} (copy)", data=wf.data)
    session.add(clone)
    await session.commit()
    return _wf_dict(clone)


@router.post("/{workflow_id}/estimate")
async def estimate(workflow_id: str, session: AsyncSession = Depends(get_session)):
    wf = await session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow 不存在")
    settings = await get_settings(session)
    price = ((settings.get("pricing") or {}).get("minimax") or {}).get("per_second")
    return estimate_workflow(json.loads(wf.data or "{}"), price_per_second=price)


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, body: RunRequest):
    try:
        result = await engine.create_run(
            workflow_id,
            trigger="manual",
            confirm_paid=body.confirm_paid,
            resume_from_run_id=body.resume_from_run_id,
            run_from_node_id=body.run_from_node_id,
        )
    except RunLimitError as e:
        raise HTTPException(409, str(e))
    except WorkflowValidationError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
    if result["status"] == "waiting_confirmation":
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=202, content=result)
    return result


@router.post("/{workflow_id}/nodes/{node_id}/run")
async def run_node(workflow_id: str, node_id: str, body: NodeRunRequest):
    """Run single node (downstream=false) or Run From Here (downstream=true)."""
    try:
        result = await engine.create_run(
            workflow_id,
            trigger="run_from_here",
            confirm_paid=True,  # 用户显式对单个节点发起，视为已确认
            run_from_node_id=node_id,
            downstream=body.downstream,
        )
    except RunLimitError as e:
        raise HTTPException(409, str(e))
    except WorkflowValidationError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
    return result


@router.delete("/{workflow_id}/nodes/{node_id}/cache")
async def clear_node_cache(workflow_id: str, node_id: str):
    deleted = await engine.clear_cache(workflow_id, node_id)
    return {"deleted": deleted}
