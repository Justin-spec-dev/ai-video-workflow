"""Shots CRUD (Shot Manager, SPEC §5.6/§6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..models.orm import Shot
from ..models.schemas import ShotUpsert

router = APIRouter(prefix="/shots", tags=["shots"])

_FIELDS = ("shot_id", "title", "prompt", "optimized_prompt", "character_context",
           "scene_context", "style_context", "input_image", "provider", "model",
           "task_id", "output_video", "last_frame", "duration", "resolution", "status")


def _shot_dict(s: Shot) -> dict:
    d = {f: getattr(s, f) for f in _FIELDS}
    d.update({"id": s.id, "workflow_id": s.workflow_id,
              "created_at": s.created_at, "updated_at": s.updated_at})
    return d


@router.get("")
async def list_shots(workflow_id: str | None = None, session: AsyncSession = Depends(get_session)):
    q = select(Shot).order_by(Shot.created_at)
    if workflow_id:
        q = q.where(Shot.workflow_id == workflow_id)
    return [_shot_dict(s) for s in (await session.execute(q)).scalars()]


@router.post("", status_code=201)
async def create_shot(body: ShotUpsert, session: AsyncSession = Depends(get_session)):
    s = Shot(workflow_id=body.workflow_id,
             **{f: getattr(body, f) for f in _FIELDS if getattr(body, f) is not None})
    session.add(s)
    await session.commit()
    return _shot_dict(s)


@router.put("/{shot_id}")
async def update_shot(shot_id: str, body: ShotUpsert, session: AsyncSession = Depends(get_session)):
    s = await session.get(Shot, shot_id)
    if s is None:
        raise HTTPException(404, "Shot 不存在")
    for f in _FIELDS:
        value = getattr(body, f)
        if value is not None:
            setattr(s, f, value)
    await session.commit()
    return _shot_dict(s)


@router.delete("/{shot_id}", status_code=204)
async def delete_shot(shot_id: str, session: AsyncSession = Depends(get_session)):
    s = await session.get(Shot, shot_id)
    if s is None:
        raise HTTPException(404, "Shot 不存在")
    await session.delete(s)
    await session.commit()
