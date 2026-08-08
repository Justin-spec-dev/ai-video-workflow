"""Image nodes: image_input（SPEC §5.2；image_preview 已移除——所有产图节点均自带内嵌预览）。"""
from __future__ import annotations

from pathlib import Path

from ..services import ffmpeg as ffmpeg_service
from ..services.files import media_dict, resolve_served_path
from ..workflow.context import NodeExecutionError
from .base import BaseNode, ConfigField, PortDef, register_node


def resolve_media_path(file_ref) -> Path:
    """Resolve a stored file reference：绝对路径、/api/files 相对路径，或上传返回的媒体 dict。"""
    if isinstance(file_ref, dict):  # 前端上传组件存的是整个 {path,url,...} 对象
        file_ref = file_ref.get("path") or file_ref.get("url") or ""
    p = Path(str(file_ref))
    if p.is_absolute() and p.is_file():
        return p
    rel = str(file_ref)
    if rel.startswith("/api/files/"):
        rel = rel[len("/api/files/"):]
    try:
        return resolve_served_path(rel)
    except (FileNotFoundError, PermissionError) as e:
        raise NodeExecutionError(f"找不到文件: {file_ref}") from e


@register_node
class ImageInputNode(BaseNode):
    type = "image_input"
    name = "Image Input"
    category = "Input"
    description = "上传/选择图片，读取宽高"
    inputs: list[PortDef] = []
    outputs = [PortDef(key="image", name="Image", type="IMAGE")]
    config_schema = [
        ConfigField(key="file", name="File", type="file", default=None),
    ]

    async def execute(self, inputs, config, context):
        file_ref = config.get("file")
        if not file_ref:
            raise NodeExecutionError("image_input 未配置文件")
        path = resolve_media_path(file_ref)
        info = await ffmpeg_service.probe(path)
        return {"image": media_dict(path, width=info.get("width"), height=info.get("height"))}
