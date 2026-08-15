"""SQLAlchemy async engine / session setup. Tables auto-created on startup."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import DATABASE_URL, ensure_dirs


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# create_all 不会为已存在的表补索引，这里对存量数据库显式补建（IF NOT EXISTS 幂等）
_EXTRA_INDEX_DDL = [
    "CREATE INDEX IF NOT EXISTS ix_noderun_wf_node_started "
    "ON node_runs (workflow_id, node_id, started_at)",
]


async def init_db() -> None:
    ensure_dirs()
    # import models so they are registered on Base.metadata
    from ..models import orm  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for ddl in _EXTRA_INDEX_DDL:
            await conn.execute(text(ddl))


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
