"""Settings persistence (settings table) + run-policy defaults (SPEC §5.7)."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.orm import Setting

DEFAULT_SETTINGS: dict = {
    "require_confirmation": True,
    "max_paid_tasks_per_run": 20,
    "max_estimated_cost_per_run": None,
    "pricing": {"minimax": {"per_second": None}},
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


async def get_settings(session: AsyncSession) -> dict:
    rows = (await session.execute(select(Setting))).scalars().all()
    stored = {}
    for r in rows:
        try:
            stored[r.key] = json.loads(r.value)
        except (TypeError, json.JSONDecodeError):
            pass
    merged = dict(DEFAULT_SETTINGS)
    flat_overrides = {k: v for k, v in stored.items()}
    return _merge(merged, flat_overrides)


async def put_settings(session: AsyncSession, updates: dict) -> dict:
    current = await get_settings(session)
    merged = _merge(current, updates)
    # store top-level keys individually
    for key in merged:
        value = json.dumps(merged[key], ensure_ascii=False)
        row = await session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
    await session.commit()
    return merged
