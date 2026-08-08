"""Files API (SPEC §6/§9): upload + safe serving with traversal protection."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..core.config import UPLOADS_DIR
from ..services import ffmpeg as ffmpeg_service
from ..services.files import resolve_served_path, unique_path, url_for_path

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload")
async def upload_file(file: UploadFile):
    filename = Path(file.filename or "upload.bin").name  # strip any client path
    target = unique_path(UPLOADS_DIR, filename)
    data = await file.read()
    target.write_bytes(data)

    width = height = None
    try:
        info = await ffmpeg_service.probe(target)
        width, height = info.get("width"), info.get("height")
    except Exception:
        pass  # 非媒体文件或 probe 失败不影响上传

    result = {"path": str(target), "url": url_for_path(target), "filename": target.name}
    if width is not None:
        result["width"] = width
    if height is not None:
        result["height"] = height
    return result


@router.get("/{path:path}")
async def serve_file(path: str):
    try:
        resolved = resolve_served_path(path)
    except PermissionError as e:
        raise HTTPException(403, "禁止访问该路径")
    except FileNotFoundError:
        raise HTTPException(404, "文件不存在")
    return FileResponse(resolved)
