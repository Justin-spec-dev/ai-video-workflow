"""Misc small routers: nodes / templates / providers / settings / health."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..nodes.base import NODE_REGISTRY
from ..providers import list_providers
from ..services.settings import get_settings, put_settings
from ..services.templates import list_templates

router = APIRouter(tags=["misc"])


@router.get("/nodes")
async def get_nodes():
    return NODE_REGISTRY.all_schemas()


@router.get("/templates")
async def get_templates():
    return list_templates()


@router.get("/providers")
async def get_providers():
    return list_providers()


@router.get("/settings")
async def read_settings(session: AsyncSession = Depends(get_session)):
    return await get_settings(session)


@router.put("/settings")
async def write_settings(updates: dict, session: AsyncSession = Depends(get_session)):
    return await put_settings(session, updates)


@router.get("/health")
async def health():
    return {"status": "ok", "node_count": len(NODE_REGISTRY.all())}
