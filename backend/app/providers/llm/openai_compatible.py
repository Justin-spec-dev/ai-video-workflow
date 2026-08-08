"""OpenAI-compatible chat completions provider (SPEC §5.3)."""
from __future__ import annotations

import httpx

from ...core.security import redact
from ..video.base import CredentialInfo, ProviderError
from .base import LLMProvider

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAICompatibleLLMProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        kwargs = {"timeout": httpx.Timeout(60.0, read=180.0)}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    @staticmethod
    def _base(credential: CredentialInfo, base_url: str | None) -> str:
        return (base_url or credential.base_url or DEFAULT_BASE_URL).rstrip("/")

    async def generate(self, *, system, prompt, context, model, temperature, max_tokens,
                       credential, base_url=None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        user = prompt or ""
        if context:
            user = f"{context}\n\n{user}" if user else context
        messages.append({"role": "user", "content": user})
        body = {
            "model": model or "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature if temperature is not None else 0.7,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        url = f"{self._base(credential, base_url)}/chat/completions"
        try:
            async with self._client() as client:
                resp = await client.post(url, headers={
                    "Authorization": f"Bearer {credential.api_key}",
                    "Content-Type": "application/json",
                }, json=body)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise ProviderError(f"LLM 网络错误: {redact(str(e))}", retryable=True) from e
        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", {})
                msg = err.get("message") or resp.text[:300]
            except Exception:
                msg = resp.text[:300]
            raise ProviderError(redact(f"LLM API 错误 (HTTP {resp.status_code}): {msg}"),
                                http_code=resp.status_code,
                                retryable=resp.status_code == 429 or resp.status_code >= 500)
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"LLM 响应格式异常: {str(data)[:300]}") from e

    async def test_connection(self, credential, base_url=None, model=None) -> tuple[bool, str]:
        url = f"{self._base(credential, base_url)}/models"
        try:
            async with self._client() as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {credential.api_key}"})
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            return False, f"连接失败: {redact(str(e))}"
        if resp.status_code == 401:
            return False, "认证失败（401）：请检查 API Key"
        if resp.status_code >= 400:
            return False, f"请求失败 (HTTP {resp.status_code})"
        return True, "连接成功"
