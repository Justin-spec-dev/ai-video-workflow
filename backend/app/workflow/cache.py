"""Cache key computation (SPEC §5.5): sha256 over (node_type, version, config, resolved_inputs).

Canvas coordinates never participate. Config keys starting with '_' (UI-only fields) are stripped.
"""
from __future__ import annotations

import hashlib
import json

UI_PREFIX = "_"


def _strip_ui(config: dict) -> dict:
    return {k: v for k, v in (config or {}).items() if not k.startswith(UI_PREFIX)}


def _normalize(value):
    """Make values JSON-deterministic."""
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value


def compute_cache_key(node_type: str, version: str, config: dict, resolved_inputs: dict) -> str:
    payload = {
        "node_type": node_type,
        "version": version,
        "config": _normalize(_strip_ui(config)),
        "inputs": _normalize(resolved_inputs or {}),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()
