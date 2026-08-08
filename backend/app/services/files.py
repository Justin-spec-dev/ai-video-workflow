"""File helpers: media dicts, URL rules, safe path resolution (SPEC §3 / §9)."""
from __future__ import annotations

import os
from pathlib import Path

from ..core.config import BACKEND_DIR, OUTPUTS_DIR, TEMP_DIR, UPLOADS_DIR


def url_for_path(abs_path: str | Path) -> str:
    """Generate the frontend-accessible /api/files/... URL for a local file.

    Rule: path relative to backend/, with 'data/uploads/' shortened to 'uploads/'.
    """
    p = Path(abs_path).resolve()
    rel = p.relative_to(BACKEND_DIR.resolve()).as_posix()
    if rel.startswith("data/uploads/"):
        rel = rel[len("data/"):]
    return f"/api/files/{rel}"


def media_dict(abs_path: str | Path, *, width=None, height=None, duration=None) -> dict:
    p = Path(abs_path)
    d = {
        "path": str(p),
        "url": url_for_path(p),
        "filename": p.name,
    }
    if width is not None:
        d["width"] = width
    if height is not None:
        d["height"] = height
    if duration is not None:
        d["duration"] = duration
    return d


ALLOWED_ROOTS = (OUTPUTS_DIR, UPLOADS_DIR, TEMP_DIR)


def resolve_served_path(rel_path: str) -> Path:
    """Resolve a /api/files/{path} target safely (directory traversal protection).

    Accepted forms:
      - 'outputs/...'  -> backend/outputs/...
      - 'temp/...'     -> backend/temp/...
      - 'uploads/...'  -> backend/data/uploads/...
      - bare '...'     -> tried under outputs/, then uploads/, then temp/
    """
    rel_path = rel_path.lstrip("/")
    if rel_path.startswith("uploads/"):
        candidate = UPLOADS_DIR / rel_path[len("uploads/"):]
        return _check(candidate)
    if rel_path.startswith("outputs/"):
        return _check(OUTPUTS_DIR / rel_path[len("outputs/"):])
    if rel_path.startswith("temp/"):
        return _check(TEMP_DIR / rel_path[len("temp/"):])
    for root in ALLOWED_ROOTS:
        candidate = root / rel_path
        try:
            return _check(candidate)
        except FileNotFoundError:
            continue
    raise FileNotFoundError(rel_path)


def _check(candidate: Path) -> Path:
    resolved = candidate.resolve()
    for root in ALLOWED_ROOTS:
        root_resolved = root.resolve()
        if resolved == root_resolved or root_resolved in resolved.parents:
            if not resolved.is_file():
                raise FileNotFoundError(str(candidate))
            return resolved
    raise PermissionError(f"Access denied: {candidate}")


def unique_path(directory: Path, filename: str) -> Path:
    """Return a non-colliding path by appending _1, _2, ... before the suffix."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    if not target.exists():
        return target
    stem, suffix = os.path.splitext(filename)
    i = 1
    while True:
        target = directory / f"{stem}_{i}{suffix}"
        if not target.exists():
            return target
        i += 1
