"""test_minimax_provider.py: MockTransport 验证 create/query/cancel 的 URL/body/header、
状态映射、错误映射、data URI 生成 (SPEC §11)."""
import base64
import json

import httpx
import pytest

from app.providers.video.base import CredentialInfo, ProviderError, VideoTaskRequest
from app.providers.video.minimax import MiniMaxVideoProvider

CRED = CredentialInfo(id="c1", name="test", kind="video", provider="minimax",
                      base_url=None, api_key="sk-testkey1234")


def make_provider(handler) -> MiniMaxVideoProvider:
    return MiniMaxVideoProvider(transport=httpx.MockTransport(handler))


async def test_create_task_url_body_headers():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "task-abc"})

    provider = make_provider(handler)
    task_id = await provider.create_task(
        VideoTaskRequest(prompt="a cat", duration=6, resolution="768P", ratio="adaptive"), CRED)

    assert task_id == "task-abc"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.minimax.io/v2/video_generation"
    assert captured["auth"] == "Bearer sk-testkey1234"
    body = captured["body"]
    assert body["model"] == "MiniMax-H3"
    assert body["content"] == [{"type": "text", "text": "a cat"}]
    assert body["resolution"] == "768P"
    assert body["duration"] == 6
    assert body["ratio"] == "16:9"  # t2va 不允许 adaptive → 默认 16:9


async def test_create_task_with_first_frame_data_uri(tmp_path):
    img = tmp_path / "frame.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_id": "t2"})

    provider = make_provider(handler)
    await provider.create_task(
        VideoTaskRequest(prompt="animate", first_frame_path=str(img), ratio="9:16"), CRED)
    body = captured["body"]
    assert body["ratio"] == "adaptive"  # 有首帧时 ratio 固定 adaptive
    image_item = body["content"][1]
    assert image_item["type"] == "image_url"
    assert image_item["role"] == "first_frame"
    url = image_item["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == img.read_bytes()


async def test_last_frame_without_first_frame_rejected(tmp_path):
    img = tmp_path / "f.png"
    img.write_bytes(b"\x89PNG" + b"0" * 10)
    provider = make_provider(lambda r: httpx.Response(200, json={"task_id": "x"}))
    with pytest.raises(ProviderError, match="first_frame"):
        await provider.create_task(
            VideoTaskRequest(prompt="p", last_frame_path=str(img)), CRED)


async def test_query_status_mapping():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://api.minimax.io/v2/query/video_generation/task-9"
        return httpx.Response(200, json={
            "task": {"id": "task-9", "status": "succeeded",
                     "content": {"url": "https://cdn.example.com/v.mp4"},
                     "ratio": "16:9", "duration": 6, "resolution": "768P"}})

    provider = make_provider(handler)
    status = await provider.get_task_status("task-9", CRED)
    assert status.status == "succeeded"
    assert status.video_url == "https://cdn.example.com/v.mp4"
    assert status.task_id == "task-9"


async def test_error_mapping_openai_style():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={
            "type": "error",
            "error": {"type": "unauthorized", "message": "invalid api key", "http_code": 401},
            "request_id": "req-1"})

    provider = make_provider(handler)
    with pytest.raises(ProviderError) as exc_info:
        await provider.create_task(VideoTaskRequest(prompt="x"), CRED)
    assert exc_info.value.http_code == 401
    assert "invalid api key" in str(exc_info.value)


async def test_retry_on_500_then_success():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500, json={"error": {"message": "server error"}})
        return httpx.Response(200, json={"task_id": "retry-ok"})

    provider = make_provider(handler)
    task_id = await provider.create_task(
        VideoTaskRequest(prompt="x", extra={"retry_count": 3}), CRED)
    assert task_id == "retry-ok"
    assert calls["n"] == 3


async def test_retry_exhausted_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    provider = make_provider(handler)
    with pytest.raises(ProviderError) as exc_info:
        await provider.create_task(
            VideoTaskRequest(prompt="x", extra={"retry_count": 1}), CRED)
    assert exc_info.value.http_code == 429
    assert exc_info.value.retryable is True


async def test_cancel():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert str(request.url) == "https://api.minimax.io/v2/video_generation/task-5"
        return httpx.Response(200, json={"task_id": "task-5", "action": "cancel", "status": "cancelled"})

    provider = make_provider(handler)
    assert await provider.cancel("task-5", CRED) is True


async def test_test_connection_401():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "page=1" in str(request.url) and "page_size=1" in str(request.url)
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    ok, msg = await make_provider(handler).test_connection(CRED)
    assert ok is False
    assert "401" in msg or "认证失败" in msg


async def test_test_connection_404_reports_unverifiable():
    ok, msg = await make_provider(lambda r: httpx.Response(404)).test_connection(CRED)
    assert ok is False
    assert "无法验证" in msg


async def test_test_connection_success():
    ok, msg = await make_provider(lambda r: httpx.Response(200, json={"tasks": []})).test_connection(CRED)
    assert ok is True


async def test_base_url_override():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"task_id": "t"})

    cred = CRED.model_copy(update={"base_url": "https://api.minimaxi.com"})
    await make_provider(handler).create_task(VideoTaskRequest(prompt="x"), cred)
    assert captured["url"].startswith("https://api.minimaxi.com/")
