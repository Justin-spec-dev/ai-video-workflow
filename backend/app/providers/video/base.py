"""Video provider base interface (SPEC §5.3)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ...nodes.base import ConfigField


class VideoTaskRequest(BaseModel):
    prompt: str
    first_frame_path: str | None = None
    last_frame_path: str | None = None
    duration: int | None = None
    resolution: str | None = None
    ratio: str | None = None
    extra: dict[str, Any] = {}


class VideoTaskStatus(BaseModel):
    task_id: str
    status: str  # queued|running|succeeded|failed|cancelled
    video_url: str | None = None
    error: str | None = None
    raw: dict[str, Any] = {}


class ProviderError(Exception):
    def __init__(self, message: str, http_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.http_code = http_code
        self.retryable = retryable


class CredentialInfo(BaseModel):
    """Decrypted credential passed to providers (never logged / serialized to API)."""
    id: str
    name: str
    kind: str
    provider: str
    base_url: str | None = None
    api_key: str


class VideoProvider:
    name: str = ""
    display_name: str = ""
    kind: str = "video"

    def config_schema(self) -> list[ConfigField]:
        return []

    async def create_task(self, request: VideoTaskRequest, credential: CredentialInfo) -> str:
        raise NotImplementedError

    async def get_task_status(self, task_id: str, credential: CredentialInfo) -> VideoTaskStatus:
        raise NotImplementedError

    async def download(self, url: str, destination: str) -> None:
        raise NotImplementedError

    async def cancel(self, task_id: str, credential: CredentialInfo) -> bool:
        return False

    async def test_connection(self, credential: CredentialInfo) -> tuple[bool, str]:
        raise NotImplementedError
