"""Video nodes: video_generation / last_frame / frame_extract / video_preview / video_merge."""
from __future__ import annotations

import asyncio
import json
import time

from ..core.events import bus
from ..core.security import redact
from ..models.orm import Task, utcnow_iso
from ..services import ffmpeg as ffmpeg_service
from ..services.files import media_dict
from ..workflow.context import NodeCancelledError, NodeExecutionError
from .base import BaseNode, ConfigField, PortDef, register_node
from .common import credential_field


@register_node
class VideoGenerationNode(BaseNode):
    type = "video_generation"
    name = "Video Generation"
    category = "Video"
    description = "调用视频生成 Provider（MiniMax H3），轮询任务并下载结果"
    is_paid = True
    inputs = [
        PortDef(key="prompt", name="Prompt", type="PROMPT", required=True),
        PortDef(key="image", name="First Frame", type="IMAGE", required=False),
        PortDef(key="last_frame_image", name="Last Frame", type="IMAGE", required=False,
                description="必须与首帧同时提供"),
    ]
    outputs = [PortDef(key="video", name="Video", type="VIDEO")]
    config_schema = [
        ConfigField(key="provider", name="Provider", type="select", options=["minimax"], default="minimax"),
        credential_field("video"),
        ConfigField(key="model", name="Model", type="model", default="MiniMax-H3"),
        ConfigField(key="resolution", name="Resolution", type="select", options=["768P", "2K"], default="768P"),
        ConfigField(key="duration", name="Duration (s)", type="number", default=6, min=4, max=15, step=1),
        ConfigField(key="ratio", name="Ratio", type="select",
                    options=["adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"], default="16:9"),
        ConfigField(key="retry_count", name="Retry Count", type="number", default=2, min=0, max=10, step=1),
        ConfigField(key="poll_interval", name="Poll Interval (s)", type="number", default=10, min=1, step=1),
        ConfigField(key="timeout", name="Timeout (s)", type="number", default=1800, min=30, step=10),
    ]

    async def execute(self, inputs, config, context):
        from ..providers import get_video_provider
        from ..providers.video.base import VideoTaskRequest

        provider_name = config.get("provider") or "minimax"
        provider = get_video_provider(provider_name)
        credential = await context.services.credentials.resolve(
            config.get("credential_id"), kind="video", provider=provider_name
        )
        image = inputs.get("image") or {}
        last_image = inputs.get("last_frame_image") or {}
        if not (inputs.get("prompt") or "").strip():
            raise NodeExecutionError(
                "提示词为空：请在上游 Prompt / 提示词优化器节点填写内容后再运行（未产生任何费用）")
        if last_image.get("path") and not image.get("path"):
            raise NodeExecutionError("MiniMax 不支持单独尾帧：last_frame 必须与首帧 image 同时提供")

        retry_count = int(config.get("retry_count") or 0)
        request = VideoTaskRequest(
            prompt=inputs.get("prompt") or "",
            first_frame_path=image.get("path"),
            last_frame_path=last_image.get("path"),
            duration=config.get("duration"),
            resolution=config.get("resolution"),
            ratio=config.get("ratio"),
            extra={"model": config.get("model") or "MiniMax-H3", "retry_count": retry_count},
        )

        # ---- create local task row + remote task ----
        session_factory = context.services.session_factory
        async with session_factory() as session:
            task = Task(
                run_id=context.run_id, workflow_id=context.workflow_id,
                node_id=context.current_node_id, provider=provider_name,
                model=config.get("model") or "MiniMax-H3",
                credential_id=config.get("credential_id"), status="queued",
                started_at=utcnow_iso(),
            )
            session.add(task)
            await session.commit()
            local_task_id = task.id
        bus.publish("task.created", {"task_id": local_task_id, "node_id": context.current_node_id})

        remote_id = None
        try:
            remote_id = await provider.create_task(request, credential)
        except Exception as e:
            # 创建失败也要把本地 task 行标记为 failed，避免永远停在 queued
            async with session_factory() as session:
                t = await session.get(Task, local_task_id)
                t.status = "failed"
                t.error = redact(str(e) or repr(e))
                t.finished_at = utcnow_iso()
                await session.commit()
            bus.publish("task.failed", {"task_id": local_task_id,
                                        "node_id": context.current_node_id,
                                        "remote_status": {"error": t.error}})
            raise
        await context.log(f"已创建远端任务 {remote_id}")
        async with session_factory() as session:
            task = await session.get(Task, local_task_id)
            task.remote_task_id = remote_id
            await session.commit()

        # ---- poll until terminal, respecting cancel_event ----
        poll_interval = float(config.get("poll_interval") or 10)
        timeout = float(config.get("timeout") or 1800)
        deadline = time.monotonic() + timeout
        status = None
        while True:
            if context.cancel_event.is_set():
                cancelled = await provider.cancel(remote_id, credential)
                if cancelled:
                    await context.log(f"远端任务 {remote_id} 已取消")
                else:
                    await context.log(
                        f"远端任务 {remote_id} 无法取消（provider 不支持或已结束），远端任务可能仍在计费",
                        level="warning")
                async with session_factory() as session:
                    t = await session.get(Task, local_task_id)
                    t.status = "cancelled"
                    t.finished_at = utcnow_iso()
                    await session.commit()
                raise NodeCancelledError()

            status = await provider.get_task_status(remote_id, credential, retries=retry_count)
            bus.publish("task.processing", {
                "task_id": local_task_id, "node_id": context.current_node_id,
                "remote_status": status.model_dump(exclude={"raw"}),
            })
            async with session_factory() as session:
                t = await session.get(Task, local_task_id)
                t.status = status.status
                t.remote_status = json.dumps(status.raw, ensure_ascii=False, default=str)
                await session.commit()

            if status.status == "succeeded":
                break
            if status.status in ("failed", "cancelled"):
                bus.publish("task.failed", {"task_id": local_task_id,
                                            "node_id": context.current_node_id,
                                            "remote_status": status.model_dump(exclude={"raw"})})
                async with session_factory() as session:
                    t = await session.get(Task, local_task_id)
                    t.error = status.error or f"远端任务 {status.status}"
                    t.finished_at = utcnow_iso()
                    await session.commit()
                raise NodeExecutionError(f"视频生成失败: {status.error or status.status}")
            if time.monotonic() > deadline:
                raise NodeExecutionError(f"视频生成超时（{int(timeout)}s），远端任务 {remote_id} 仍在运行")
            # interruptible sleep
            try:
                await asyncio.wait_for(context.cancel_event.wait(), timeout=poll_interval)
            except asyncio.TimeoutError:
                pass

        # ---- download result ----
        if not status.video_url:
            raise NodeExecutionError("任务成功但响应中没有视频 URL")
        out_dir = context.node_output_dir(context.current_node_id)
        dest = out_dir / "video.mp4"
        await provider.download(status.video_url, str(dest))
        info = await ffmpeg_service.probe(dest)
        video = media_dict(dest, width=info.get("width"), height=info.get("height"),
                           duration=info.get("duration"))
        async with session_factory() as session:
            t = await session.get(Task, local_task_id)
            t.status = "succeeded"
            t.output = json.dumps(video, ensure_ascii=False)
            t.finished_at = utcnow_iso()
            await session.commit()
        bus.publish("task.success", {"task_id": local_task_id, "node_id": context.current_node_id})
        return {"video": video}


@register_node
class LastFrameNode(BaseNode):
    type = "last_frame"
    name = "Last Frame"
    category = "Video"
    description = "FFmpeg 提取视频最后一帧"
    inputs = [PortDef(key="video", name="Video", type="VIDEO", required=True)]
    outputs = [PortDef(key="image", name="Image", type="IMAGE")]
    config_schema: list[ConfigField] = []

    async def execute(self, inputs, config, context):
        video = inputs.get("video") or {}
        if not video.get("path"):
            raise NodeExecutionError("last_frame 输入缺少视频 path")
        out = context.node_output_dir(context.current_node_id) / "last_frame.png"
        result = await ffmpeg_service.extract_frame(video["path"], out, mode="last")
        return {"image": media_dict(result["path"], width=result.get("width"), height=result.get("height"))}


@register_node
class FrameExtractNode(BaseNode):
    type = "frame_extract"
    name = "Frame Extract"
    category = "Video"
    description = "按 first/last/timestamp/percentage 提取视频帧"
    inputs = [PortDef(key="video", name="Video", type="VIDEO", required=True)]
    outputs = [PortDef(key="image", name="Image", type="IMAGE")]
    config_schema = [
        ConfigField(key="mode", name="Mode", type="select",
                    options=["first", "last", "timestamp", "percentage"], default="first"),
        ConfigField(key="timestamp", name="Timestamp (s)", type="number", default=0, min=0, step=0.1),
        ConfigField(key="percentage", name="Percentage (0-100)", type="number", default=50, min=0, max=100, step=1),
    ]

    async def execute(self, inputs, config, context):
        video = inputs.get("video") or {}
        if not video.get("path"):
            raise NodeExecutionError("frame_extract 输入缺少视频 path")
        mode = config.get("mode") or "first"
        out = context.node_output_dir(context.current_node_id) / f"frame_{mode}.png"
        result = await ffmpeg_service.extract_frame(
            video["path"], out, mode=mode,
            timestamp=config.get("timestamp"), percentage=config.get("percentage"),
        )
        return {"image": media_dict(result["path"], width=result.get("width"), height=result.get("height"))}


@register_node
class VideoPreviewNode(BaseNode):
    type = "video_preview"
    name = "Video Preview"
    category = "Video"
    description = "视频预览（透传）"
    inputs = [PortDef(key="video", name="Video", type="VIDEO", required=True)]
    outputs = [PortDef(key="video", name="Video", type="VIDEO")]
    config_schema: list[ConfigField] = []

    async def execute(self, inputs, config, context):
        return {"video": inputs.get("video")}


@register_node
class VideoMergeNode(BaseNode):
    type = "video_merge"
    name = "Video Merge"
    category = "Video"
    description = "按顺序合并多个视频（先 stream copy，失败回退 re-encode）"
    inputs = [PortDef(key="videos", name="Videos", type="VIDEO[]", required=True, multiple=True)]
    outputs = [PortDef(key="video", name="Video", type="VIDEO")]
    config_schema = [
        ConfigField(key="reencode", name="Re-encode", type="select", options=["auto", "always"], default="auto"),
    ]

    async def execute(self, inputs, config, context):
        videos = inputs.get("videos") or []
        if isinstance(videos, dict):  # single connection edge case
            videos = [videos]
        paths = [v["path"] for v in videos if isinstance(v, dict) and v.get("path")]
        if not paths:
            raise NodeExecutionError("video_merge 没有可用输入视频")
        out_dir = context.node_output_dir(context.current_node_id)
        dest = out_dir / "merged.mp4"
        await ffmpeg_service.merge(paths, dest, reencode=config.get("reencode") or "auto", work_dir=out_dir)
        info = await ffmpeg_service.probe(dest)
        return {"video": media_dict(dest, width=info.get("width"), height=info.get("height"),
                                    duration=info.get("duration"))}
