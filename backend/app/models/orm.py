"""SQLAlchemy ORM models (SPEC §5.6). All timestamps stored as ISO strings."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_uuid() -> str:
    import uuid

    return uuid.uuid4().hex[:12]


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_short_uuid)
    name: Mapped[str] = mapped_column(String(255), default="Untitled")
    data: Mapped[str] = mapped_column(Text, default="{}")  # workflow JSON (SPEC §4)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso, onupdate=utcnow_iso)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_short_uuid)
    workflow_id: Mapped[str] = mapped_column(String(32), ForeignKey("workflows.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    # running/success/failed/cancelled/waiting_confirmation
    trigger: Mapped[str] = mapped_column(String(32), default="manual")  # manual/resume/run_from_here
    cost_estimate: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class NodeRun(Base):
    __tablename__ = "node_runs"
    __table_args__ = (
        # 热路径查询：run_from_here 回填/历史回填按 (workflow_id, node_id) 取最近成功输出
        Index("ix_noderun_wf_node_started", "workflow_id", "node_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_short_uuid)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("workflow_runs.id"), index=True)
    workflow_id: Mapped[str] = mapped_column(String(32), index=True)
    node_id: Mapped[str] = mapped_column(String(64))
    node_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    inputs: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    outputs: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    cache_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    credential_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_short_uuid)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    workflow_id: Mapped[str] = mapped_column(String(32), index=True)
    node_id: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    credential_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    remote_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    remote_status: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    output: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_short_uuid)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(16))  # llm | video
    provider: Mapped[str] = mapped_column(String(64))
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    secret_encrypted: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso, onupdate=utcnow_iso)


class CacheEntry(Base):
    __tablename__ = "cache"
    __table_args__ = (UniqueConstraint("workflow_id", "node_id", "cache_key", name="uq_cache"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_short_uuid)
    workflow_id: Mapped[str] = mapped_column(String(32), index=True)
    node_id: Mapped[str] = mapped_column(String(64))
    cache_key: Mapped[str] = mapped_column(String(64))
    outputs: Mapped[str] = mapped_column(Text)  # JSON
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)  # JSON


class Shot(Base):
    __tablename__ = "shots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_short_uuid)
    workflow_id: Mapped[str] = mapped_column(String(32), index=True)
    shot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    optimized_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_video: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_frame: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[str | None] = mapped_column(String(16), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(40), default=utcnow_iso, onupdate=utcnow_iso)
