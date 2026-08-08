"""Provider registries."""
from __future__ import annotations

from .llm.openai_compatible import OpenAICompatibleLLMProvider
from .video.base import VideoProvider
from .video.minimax import MiniMaxVideoProvider

_llm_providers = {"openai_compatible": OpenAICompatibleLLMProvider}
_video_providers = {"minimax": MiniMaxVideoProvider}


def get_llm_provider(name: str) -> OpenAICompatibleLLMProvider:
    cls = _llm_providers.get(name)
    if cls is None:
        raise ValueError(f"未知 LLM provider: {name}")
    return cls()


def get_video_provider(name: str) -> VideoProvider:
    cls = _video_providers.get(name)
    if cls is None:
        raise ValueError(f"未知 video provider: {name}")
    return cls()


def list_providers() -> list[dict]:
    out = []
    for cls in _llm_providers.values():
        inst = cls()
        out.append({"name": inst.name, "display_name": "OpenAI Compatible", "kind": "llm", "config_schema": []})
    for cls in _video_providers.values():
        inst = cls()
        out.append({
            "name": inst.name,
            "display_name": inst.display_name,
            "kind": "video",
            "config_schema": [c.model_dump() for c in inst.config_schema()],
        })
    return out
