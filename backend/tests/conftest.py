import json

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    """Fresh sqlite DB per test."""
    from app.core.database import Base

    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    sf = async_sessionmaker(eng, expire_on_commit=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield sf
    await eng.dispose()


@pytest_asyncio.fixture
async def client(session_factory, monkeypatch, tmp_path):
    """httpx AsyncClient over ASGITransport, with all DB access redirected to the test DB."""
    import httpx

    import app.core.database as db
    import app.workflow.engine as engine_mod
    from app.main import app

    engine_mod.engine.session_factory = session_factory
    engine_mod.engine.active.clear()
    monkeypatch.setattr(engine_mod, "OUTPUTS_DIR", tmp_path / "outputs")

    async def override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[db.get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def make_workflow(session_factory, data: dict, name: str = "test-wf") -> str:
    from app.models.orm import Workflow

    async with session_factory() as session:
        wf = Workflow(name=name, data=json.dumps(data, ensure_ascii=False))
        session.add(wf)
        await session.commit()
        return wf.id
