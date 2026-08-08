"""LLM provider base interface (SPEC §5.3)."""
from __future__ import annotations


class LLMProvider:
    name: str = ""
    kind: str = "llm"

    async def generate(self, *, system, prompt, context, model, temperature, max_tokens,
                       credential, base_url=None) -> str:
        raise NotImplementedError

    async def test_connection(self, credential, base_url=None, model=None) -> tuple[bool, str]:
        raise NotImplementedError
