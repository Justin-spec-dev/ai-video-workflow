"""Tasks API (SPEC §6): remote provider task tracking."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..credentials.service import CredentialService
from ..models.orm import Task, utcnow_iso
from ..providers import get_video_provider

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_dict(t: Task) -> dict:
    return {
        "id": t.id, "run_id": t.run_id, "workflow_id": t.workflow_id, "node_id": t.node_id,
        "provider": t.provider, "model": t.model, "credential_id": t.credential_id,
        "remote_task_id": t.remote_task_id, "status": t.status,
        "remote_status": json.loads(t.remote_status) if t.remote_status else None,
        "output": json.loads(t.output) if t.output else None,
        "error": t.error,
        "created_at": t.created_at, "started_at": t.started_at, "finished_at": t.finished_at,
    }


@router.get("")
async def list_tasks(workflow_id: str | None = None, status: str | None = None,
                     session: AsyncSession = Depends(get_session)):
    q = select(Task).order_by(Task.created_at.desc())
    if workflow_id:
        q = q.where(Task.workflow_id == workflow_id)
    if status:
        q = q.where(Task.status == status)
    return [_task_dict(t) for t in (await session.execute(q)).scalars()]


@router.get("/{task_id}")
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)):
    t = await session.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "Task 不存在")
    return _task_dict(t)


@router.post("/{task_id}/refresh")
async def refresh_task(task_id: str, session: AsyncSession = Depends(get_session)):
    t = await session.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "Task 不存在")
    if not t.remote_task_id:
        raise HTTPException(400, "Task 还没有 remote_task_id")
    credential = await CredentialService(session).resolve(t.credential_id, kind="video", provider=t.provider)
    provider = get_video_provider(t.provider)
    status = await provider.get_task_status(t.remote_task_id, credential)
    t.status = status.status
    t.remote_status = json.dumps(status.raw, ensure_ascii=False, default=str)
    if status.status in ("succeeded", "failed", "cancelled"):
        t.finished_at = utcnow_iso()
        if status.error:
            t.error = status.error
    await session.commit()
    return _task_dict(t)


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, session: AsyncSession = Depends(get_session)):
    t = await session.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "Task 不存在")
    if not t.remote_task_id:
        raise HTTPException(400, "Task 还没有 remote_task_id")
    credential = await CredentialService(session).resolve(t.credential_id, kind="video", provider=t.provider)
    provider = get_video_provider(t.provider)
    ok = await provider.cancel(t.remote_task_id, credential)
    if not ok:
        raise HTTPException(400, "Provider 不支持取消，或远端任务已结束（可能仍在计费）")
    t.status = "cancelled"
    t.finished_at = utcnow_iso()
    await session.commit()
    return _task_dict(t)
