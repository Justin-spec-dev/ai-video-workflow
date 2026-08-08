"""Pydantic request/response schemas for the REST API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    name: str = "Untitled"
    data: dict | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    data: dict | None = None


class RunRequest(BaseModel):
    confirm_paid: bool = False
    resume_from_run_id: str | None = None
    run_from_node_id: str | None = None


class NodeRunRequest(BaseModel):
    downstream: bool = True


class CredentialCreate(BaseModel):
    name: str
    kind: Literal["llm", "video"]
    provider: str
    api_key: str
    base_url: str | None = None
    is_default: bool = False


class CredentialUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # 空白/None = 不变
    is_default: bool | None = None


class ShotUpsert(BaseModel):
    workflow_id: str
    shot_id: str | None = None
    title: str | None = None
    prompt: str | None = None
    optimized_prompt: str | None = None
    character_context: str | None = None
    scene_context: str | None = None
    style_context: str | None = None
    input_image: str | None = None
    provider: str | None = None
    model: str | None = None
    task_id: str | None = None
    output_video: str | None = None
    last_frame: str | None = None
    duration: str | None = None
    resolution: str | None = None
    status: str | None = None


SECRET_KEYS = {"api_key", "apikey", "secret", "secret_encrypted", "token", "password"}


def assert_no_secrets(data: Any, path: str = "data") -> None:
    """Workflow JSON must never contain secrets (SPEC §4/§9)."""
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str) and k.lower() in SECRET_KEYS:
                raise ValueError(f"Workflow JSON 禁止包含 secret 字段: {path}.{k}")
            assert_no_secrets(v, f"{path}.{k}")
    elif isinstance(data, list):
        for i, v in enumerate(data):
            assert_no_secrets(v, f"{path}[{i}]")
