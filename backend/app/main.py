"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import ensure_dirs
from .core.database import init_db
from .core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    ensure_dirs()
    await init_db()
    yield


app = FastAPI(title="AI Video Workflow Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .api import credentials as credentials_api  # noqa: E402
from .api import files as files_api  # noqa: E402
from .api import misc as misc_api  # noqa: E402
from .api import runs as runs_api  # noqa: E402
from .api import shots as shots_api  # noqa: E402
from .api import tasks as tasks_api  # noqa: E402
from .api import workflows as workflows_api  # noqa: E402
from .api import ws as ws_api  # noqa: E402

app.include_router(misc_api.router, prefix="/api")
app.include_router(workflows_api.router, prefix="/api")
app.include_router(runs_api.router, prefix="/api")
app.include_router(tasks_api.router, prefix="/api")
app.include_router(credentials_api.router, prefix="/api")
app.include_router(files_api.router, prefix="/api")
app.include_router(shots_api.router, prefix="/api")
app.include_router(ws_api.router)
