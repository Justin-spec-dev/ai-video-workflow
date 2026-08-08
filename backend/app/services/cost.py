"""Cost estimation / protection (SPEC §5.7)."""
from __future__ import annotations

from ..nodes.base import NODE_REGISTRY

_LLM_NODE_TYPES = {"llm", "prompt_optimizer", "storyboard"}


def estimate_workflow(data: dict, *, price_per_second: float | None = None) -> dict:
    """Static analysis of workflow JSON."""
    nodes = data.get("nodes", [])
    notes: list[str] = []
    paid_count = 0
    api_calls = 0
    video_seconds = 0.0

    for n in nodes:
        cls = NODE_REGISTRY.get(n.get("type", ""))
        if cls is None:
            continue
        if cls.is_paid:
            paid_count += 1
            api_calls += 1
            duration = (n.get("config") or {}).get("duration")
            try:
                video_seconds += float(duration) if duration else 6.0
            except (TypeError, ValueError):
                video_seconds += 6.0
        elif n.get("type") in _LLM_NODE_TYPES:
            api_calls += 1

    estimated_cost = None
    if video_seconds > 0:
        if price_per_second is not None:
            estimated_cost = round(video_seconds * float(price_per_second), 4)
        else:
            notes.append("Cost unavailable: 未设置 pricing.minimax.per_second（可在 Settings 中填写单价）")
    if paid_count == 0:
        notes.append("该工作流不含付费节点")

    return {
        "paid_node_count": paid_count,
        "estimated_api_calls": api_calls,
        "estimated_video_seconds": video_seconds,
        "estimated_cost": estimated_cost,
        "currency": "USD",
        "notes": notes,
    }
