"""Output node: save_file (SPEC §5.2)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..core.config import OUTPUTS_DIR
from ..services.files import media_dict, unique_path
from ..workflow.context import NodeExecutionError
from .base import BaseNode, ConfigField, PortDef, register_node


@register_node
class SaveFileNode(BaseNode):
    type = "save_file"
    name = "Save File"
    category = "Output"
    description = "把 video/image/text/json 保存到指定目录"
    inputs = [
        PortDef(key="video", name="Video", type="VIDEO", required=False),
        PortDef(key="image", name="Image", type="IMAGE", required=False),
        PortDef(key="text", name="Text", type="TEXT", required=False),
        PortDef(key="json", name="JSON", type="JSON", required=False),
    ]
    outputs = [PortDef(key="file", name="File", type="FILE")]
    config_schema = [
        ConfigField(key="directory", name="Directory", type="text", default="saved",
                    description="相对 backend/outputs/ 或绝对路径"),
        ConfigField(key="filename", name="Filename", type="text", default="",
                    description="留空则沿用源文件名"),
        ConfigField(key="overwrite", name="On Conflict", type="select",
                    options=["overwrite", "rename", "fail"], default="rename"),
    ]

    async def execute(self, inputs, config, context):
        source_path: Path | None = None
        content: bytes | None = None
        default_name = "output.bin"

        if inputs.get("video") and inputs["video"].get("path"):
            source_path = Path(inputs["video"]["path"])
        elif inputs.get("image") and inputs["image"].get("path"):
            source_path = Path(inputs["image"]["path"])
        elif inputs.get("text") is not None:
            content = str(inputs["text"]).encode()
            default_name = "output.txt"
        elif inputs.get("json") is not None:
            content = json.dumps(inputs["json"], ensure_ascii=False, indent=2).encode()
            default_name = "output.json"
        else:
            raise NodeExecutionError("save_file 没有任何非空输入")

        directory = (config.get("directory") or "saved").strip()
        out_dir = Path(directory) if Path(directory).is_absolute() else OUTPUTS_DIR / directory
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = (config.get("filename") or "").strip()
        if not filename:
            filename = source_path.name if source_path else default_name
        target = out_dir / filename

        mode = config.get("overwrite") or "rename"
        if target.exists():
            if mode == "fail":
                raise NodeExecutionError(f"目标文件已存在: {target}")
            if mode == "rename":
                target = unique_path(out_dir, filename)

        if source_path is not None:
            shutil.copyfile(source_path, target)
        else:
            target.write_bytes(content)

        await context.log(f"已保存文件: {target}")
        return {"file": media_dict(target)}
