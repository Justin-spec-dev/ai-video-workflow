"""ExecutionContext passed to every node execute() (SPEC §5.5 context.py)."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.events import bus
from ..core.security import redact

logger = logging.getLogger("workflow")


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", (name or "workflow").strip().lower()).strip("-")
    return s or "workflow"


@dataclass
class ServiceRegistry:
    """Services available to nodes via context.services."""
    ffmpeg: Any = None          # app.services.ffmpeg module
    credentials: Any = None     # CredentialService-like (works on its own sessions)
    http_client: Any = None     # callable -> httpx.AsyncClient
    session_factory: Any = None  # async_sessionmaker for task rows etc.


@dataclass
class ExecutionContext:
    workflow_id: str
    run_id: str
    node_results: dict[str, dict] = field(default_factory=dict)   # node_id -> outputs dict
    node_statuses: dict[str, str] = field(default_factory=dict)   # node_id -> status
    variables: dict[str, Any] = field(default_factory=dict)
    output_dir: Path = Path(".")
    start_time: float = field(default_factory=time.time)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    services: ServiceRegistry = field(default_factory=ServiceRegistry)
    current_node_id: str = ""   # set by the engine while a node executes
    force_rerun: set[str] = field(default_factory=set)  # run_from_here: 绕过缓存的节点

    def node_output_dir(self, node_id: str) -> Path:
        """outputs/<wf-slug>/run_<ts>/nodes/<node_id>/"""
        d = self.output_dir / "nodes" / node_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def log(self, message: str, level: str = "info", node_id: str | None = None) -> None:
        message = redact(str(message))
        log_fn = getattr(logger, level if level in ("debug", "info", "warning", "error") else "info")
        log_fn(f"[run {self.run_id}] {node_id or '-'}: {message}")
        bus.publish("log", {
            "run_id": self.run_id,
            "node_id": node_id,
            "level": level,
            "message": message,
        })

    def check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise NodeCancelledError()


class NodeCancelledError(Exception):
    """Raised by nodes when the run's cancel_event is set."""


class NodeExecutionError(Exception):
    """Raised by nodes for business-level failures (recorded as node FAILED)."""
