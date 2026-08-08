"""test_ffmpeg.py: last_frame / merge（用 ffmpeg 生成 1s 测试视频）(SPEC §11)."""
import asyncio

import pytest

from app.services import ffmpeg as ff


async def _make_video(path, duration=1, size="320x240"):
    cmd = [
        ff.ffmpeg_path(), "-y", "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size={size}:rate=10",
        "-pix_fmt", "yuv420p", str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    assert proc.returncode == 0, err.decode()[-500:]


@pytest.fixture
async def video(tmp_path):
    p = tmp_path / "src.mp4"
    await _make_video(p)
    return p


async def test_ffmpeg_binary_found():
    assert ff.ffmpeg_path()
    assert ff.ffprobe_path()


async def test_probe(video):
    info = await ff.probe(video)
    assert info["width"] == 320
    assert info["height"] == 240
    assert abs(info["duration"] - 1.0) < 0.2


async def test_extract_last_frame(video, tmp_path):
    out = tmp_path / "last.png"
    result = await ff.extract_frame(video, out, mode="last")
    assert out.exists() and out.stat().st_size > 0
    assert result["width"] == 320


async def test_extract_first_and_timestamp(video, tmp_path):
    first = tmp_path / "first.png"
    await ff.extract_frame(video, first, mode="first")
    assert first.exists()
    ts = tmp_path / "ts.png"
    await ff.extract_frame(video, ts, mode="timestamp", timestamp=0.5)
    assert ts.exists()
    pct = tmp_path / "pct.png"
    await ff.extract_frame(video, pct, mode="percentage", percentage=50)
    assert pct.exists()


async def test_merge_stream_copy(video, tmp_path):
    out = tmp_path / "merged.mp4"
    await ff.merge([video, video], out, work_dir=tmp_path)
    assert out.exists() and out.stat().st_size > 0
    info = await ff.probe(out)
    assert abs(info["duration"] - 2.0) < 0.4


async def test_merge_reencode(video, tmp_path):
    out = tmp_path / "merged_re.mp4"
    await ff.merge([video, video], out, reencode="always", work_dir=tmp_path)
    info = await ff.probe(out)
    assert abs(info["duration"] - 2.0) < 0.4
