"""FFmpeg service wrapper: extract_frame / merge / probe (SPEC §5, ffmpeg service)."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

from ..core.config import PROJECT_FFMPEG_DIR


class FFmpegNotFoundError(RuntimeError):
    pass


def _find_binary(name: str) -> str:
    env = os.environ.get("FFMPEG_PATH", "").strip()
    candidates: list[Path] = []
    if env:
        p = Path(env)
        candidates.append(p / name if p.is_dir() else p)
        if name == "ffprobe" and not p.is_dir():
            candidates.append(p.with_name("ffprobe"))
    candidates.append(PROJECT_FFMPEG_DIR / name)
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    on_path = shutil.which(name)
    if on_path:
        return on_path
    raise FFmpegNotFoundError(
        f"找不到 {name}。请设置 FFMPEG_PATH，或将二进制放到 {PROJECT_FFMPEG_DIR}/，或安装到系统 PATH。"
    )


def ffmpeg_path() -> str:
    return _find_binary("ffmpeg")


def ffprobe_path() -> str:
    return _find_binary("ffprobe")


async def _run(cmd: list[str]) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, (err or out).decode(errors="replace")


async def probe(path: str | Path) -> dict:
    """Return {'width': int|None, 'height': int|None, 'duration': float|None}."""
    ffprobe = ffprobe_path()
    cmd = [
        ffprobe, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {err.decode(errors='replace')[:500]}")
    data = json.loads(out.decode())
    width = height = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") in ("video", "image") or stream.get("width"):
            width = stream.get("width")
            height = stream.get("height")
            break
    duration = None
    fmt = data.get("format") or {}
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            duration = None
    return {"width": width, "height": height, "duration": duration}


async def extract_frame(
    video_path: str | Path,
    output_path: str | Path,
    *,
    mode: str = "last",
    timestamp: float | None = None,
    percentage: float | None = None,
) -> dict:
    """Extract a frame as PNG. mode: first/last/timestamp/percentage."""
    ffmpeg = ffmpeg_path()
    video_path = str(video_path)
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if mode == "first":
        cmd = [ffmpeg, "-y", "-i", video_path, "-frames:v", "1", output_path]
    elif mode == "last":
        # seek from end; -sseof before -i is fast and accurate enough for the last frame
        cmd = [ffmpeg, "-y", "-sseof", "-1", "-i", video_path, "-update", "1", "-frames:v", "1", output_path]
    elif mode == "timestamp":
        if timestamp is None:
            raise ValueError("mode=timestamp 需要 timestamp 参数")
        cmd = [ffmpeg, "-y", "-ss", str(timestamp), "-i", video_path, "-frames:v", "1", output_path]
    elif mode == "percentage":
        if percentage is None:
            raise ValueError("mode=percentage 需要 percentage 参数")
        info = await probe(video_path)
        if not info.get("duration"):
            raise RuntimeError("无法获取视频时长，percentage 模式失败")
        ts = max(0.0, float(info["duration"]) * float(percentage) / 100.0)
        cmd = [ffmpeg, "-y", "-ss", str(ts), "-i", video_path, "-frames:v", "1", output_path]
    else:
        raise ValueError(f"未知 mode: {mode}")

    code, log = await _run(cmd)
    if code != 0 or not Path(output_path).exists():
        raise RuntimeError(f"ffmpeg 提取帧失败 (mode={mode}): {log[-800:]}")
    info = await probe(output_path)
    return {"path": output_path, "width": info.get("width"), "height": info.get("height")}


async def merge(
    video_paths: list[str | Path],
    output_path: str | Path,
    *,
    reencode: str = "auto",
    work_dir: str | Path | None = None,
) -> str:
    """Concat videos. Try stream copy (concat demuxer) first, fall back to libx264 re-encode."""
    ffmpeg = ffmpeg_path()
    if not video_paths:
        raise ValueError("video_merge 需要至少一个输入视频")
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    work = Path(work_dir) if work_dir else Path(output_path).parent
    work.mkdir(parents=True, exist_ok=True)
    list_file = work / "concat_list.txt"
    list_file.write_text(
        "".join(f"file '{Path(p).resolve()}'\n" for p in video_paths), encoding="utf-8"
    )

    async def _copy() -> bool:
        cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", output_path]
        code, _ = await _run(cmd)
        return code == 0 and Path(output_path).exists() and Path(output_path).stat().st_size > 0

    async def _reencode() -> None:
        cmd = [
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", output_path,
        ]
        code, log = await _run(cmd)
        if code != 0 or not Path(output_path).exists():
            raise RuntimeError(f"ffmpeg 合并失败: {log[-800:]}")

    if reencode == "always":
        await _reencode()
    else:
        if not await _copy():
            await _reencode()
    try:
        list_file.unlink()
    except OSError:
        pass
    return output_path
