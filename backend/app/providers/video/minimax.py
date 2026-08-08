"""MiniMax H3 video generation provider (SPEC §5.3 — strictly per verified official API)."""
from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path

import httpx

from ...core.security import redact
from ...nodes.base import ConfigField
from .base import CredentialInfo, ProviderError, VideoProvider, VideoTaskRequest, VideoTaskStatus

DEFAULT_BASE_URL = "https://api.minimax.io"
MAX_IMAGE_BYTES = 30 * 1024 * 1024   # 30MB per image
MAX_BODY_BYTES = 64 * 1024 * 1024    # 64MB request body

RATIOS = ["adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]
RESOLUTIONS = ["768P", "2K"]


class MiniMaxVideoProvider(VideoProvider):
    name = "minimax"
    display_name = "MiniMax (H3)"

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    def config_schema(self) -> list[ConfigField]:
        return [
            ConfigField(key="model", name="Model", type="model", default="MiniMax-H3"),
            ConfigField(key="resolution", name="Resolution", type="select", options=RESOLUTIONS, default="768P"),
            ConfigField(key="duration", name="Duration (s)", type="number", default=6, min=4, max=15, step=1),
            ConfigField(key="ratio", name="Ratio", type="select", options=RATIOS, default="16:9"),
        ]

    def _base(self, credential: CredentialInfo) -> str:
        return (credential.base_url or DEFAULT_BASE_URL).rstrip("/")

    def _client(self) -> httpx.AsyncClient:
        kwargs = {"timeout": httpx.Timeout(60.0, read=300.0)}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    def _headers(self, credential: CredentialInfo) -> dict:
        return {
            "Authorization": f"Bearer {credential.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _image_to_data_uri(path: str) -> str:
        p = Path(path)
        if not p.is_file():
            raise ProviderError(f"图片文件不存在: {path}")
        size = p.stat().st_size
        if size > MAX_IMAGE_BYTES:
            raise ProviderError(f"图片超过 30MB 限制 ({size / 1024 / 1024:.1f}MB): {p.name}")
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f"data:{mime};base64,{b64}"

    def _build_content(self, request: VideoTaskRequest) -> list[dict]:
        content: list[dict] = [{"type": "text", "text": request.prompt}]
        if request.last_frame_path and not request.first_frame_path:
            raise ProviderError("MiniMax 要求 last_frame 必须与 first_frame 同时提供（不支持单独尾帧）")
        if request.first_frame_path:
            content.append({
                "type": "image_url",
                "image_url": {"url": self._image_to_data_uri(request.first_frame_path)},
                "role": "first_frame",
            })
        if request.last_frame_path:
            content.append({
                "type": "image_url",
                "image_url": {"url": self._image_to_data_uri(request.last_frame_path)},
                "role": "last_frame",
            })
        return content

    def _build_body(self, request: VideoTaskRequest) -> dict:
        has_frames = bool(request.first_frame_path)
        content = self._build_content(request)
        if has_frames:
            ratio = "adaptive"  # 有首/尾帧时 ratio 固定 adaptive
        else:
            ratio = request.ratio or "16:9"
            if ratio == "adaptive":
                ratio = "16:9"  # t2va 不允许 adaptive，默认 16:9
        body = {
            "model": request.extra.get("model") or "MiniMax-H3",
            "content": content,
            "resolution": request.resolution or "768P",
            "duration": int(request.duration or 6),
            "ratio": ratio,
        }
        return body

    @staticmethod
    def _parse_error(resp: httpx.Response) -> ProviderError:
        retryable = resp.status_code == 429 or resp.status_code >= 500
        try:
            data = resp.json()
            err = data.get("error") or {}
            msg = err.get("message") or data.get("message") or resp.text[:300]
        except Exception:
            msg = resp.text[:300]
        return ProviderError(redact(f"MiniMax API 错误 (HTTP {resp.status_code}): {msg}"),
                             http_code=resp.status_code, retryable=retryable)

    async def _request(self, method: str, url: str, credential: CredentialInfo,
                       json_body: dict | None = None, retries: int = 0) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                async with self._client() as client:
                    resp = await client.request(method, url, headers=self._headers(credential), json=json_body)
                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt < retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise self._parse_error(resp)
                if resp.status_code >= 400:
                    raise self._parse_error(resp)
                return resp
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_exc = e
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise ProviderError(f"网络错误: {redact(str(e))}", retryable=True) from e
        raise ProviderError(f"请求失败: {last_exc}")

    async def create_task(self, request: VideoTaskRequest, credential: CredentialInfo) -> str:
        body = self._build_body(request)
        import json as _json
        if len(_json.dumps(body).encode()) > MAX_BODY_BYTES:
            raise ProviderError("请求体超过 64MB 限制，请减小输入图片")
        retries = int(request.extra.get("retry_count", 0) or 0)
        resp = await self._request("POST", f"{self._base(credential)}/v2/video_generation",
                                   credential, json_body=body, retries=retries)
        data = resp.json()
        task_id = data.get("task_id")
        if not task_id:
            raise ProviderError(f"MiniMax 响应缺少 task_id: {str(data)[:300]}")
        return str(task_id)

    async def get_task_status(self, task_id: str, credential: CredentialInfo,
                              retries: int = 0) -> VideoTaskStatus:
        resp = await self._request("GET", f"{self._base(credential)}/v2/query/video_generation/{task_id}",
                                   credential, retries=retries)
        data = resp.json()
        task = data.get("task") or {}
        content = task.get("content") or {}
        err = task.get("error")
        err_msg = None
        if err:
            err_msg = err.get("message") if isinstance(err, dict) else str(err)
        return VideoTaskStatus(
            task_id=str(task.get("id") or task_id),
            status=task.get("status") or "queued",
            video_url=content.get("url"),
            error=err_msg,
            raw=data,
        )

    async def download(self, url: str, destination: str) -> None:
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        async with self._client() as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    raise ProviderError(f"下载视频失败 (HTTP {resp.status_code})", http_code=resp.status_code)
                with open(destination, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=1 << 16):
                        f.write(chunk)

    async def cancel(self, task_id: str, credential: CredentialInfo) -> bool:
        try:
            resp = await self._request("DELETE", f"{self._base(credential)}/v2/video_generation/{task_id}",
                                       credential)
            data = resp.json()
            return bool(data.get("task_id"))
        except ProviderError:
            return False

    async def test_connection(self, credential: CredentialInfo) -> tuple[bool, str]:
        try:
            async with self._client() as client:
                resp = await client.get(
                    f"{self._base(credential)}/v2/query/video_generation",
                    headers=self._headers(credential),
                    params={"page": 1, "page_size": 1},
                )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            return False, f"连接失败: {redact(str(e))}"
        if resp.status_code == 401:
            return False, "认证失败（401）：请检查 API Key"
        if resp.status_code == 404:
            return False, "无法验证（端点不可用，404）"
        if resp.status_code >= 400:
            return False, f"请求失败 (HTTP {resp.status_code})"
        return True, "连接成功"
