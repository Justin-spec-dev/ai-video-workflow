"""Cache key computation (SPEC §5.5): sha256 over (node_type, version, config, resolved_inputs).

Canvas coordinates never participate. Config keys starting with '_' (UI-only fields) are stripped.

Media inputs (IMAGE/VIDEO) are identified by file fingerprint (size + mtime_ns) instead of the
absolute path: output paths embed per-run timestamps (outputs/<slug>/run_<ts>_<id>/...), so a
path-based key would change on every run and the cache would never hit for any node downstream
of a media-producing node (LastFrame / FrameExtract / VideoMerge / image-to-video, ...).
"""
from __future__ import annotations

import hashlib
import json
import os

UI_PREFIX = "_"


def _strip_ui(config: dict) -> dict:
    return {k: v for k, v in (config or {}).items() if not k.startswith(UI_PREFIX)}


def _media_fingerprint(path: str) -> str | None:
    """Cheap content identity for a media file: (size, mtime_ns) from stat() — O(1), no read."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return f"{st.st_size}:{st.st_mtime_ns}"


def _normalize(value):
    """Make values JSON-deterministic; media dicts are replaced by their content fingerprint."""
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str) and path:
            fp = _media_fingerprint(path)
            if fp is not None:
                return {"__media__": fp}
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
