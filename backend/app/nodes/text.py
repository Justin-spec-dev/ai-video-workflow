"""Text nodes: prompt / text / combine_prompt (SPEC §5.2)."""
from __future__ import annotations

from .base import BaseNode, ConfigField, PortDef, register_node
from .common import render_template


@register_node
class PromptNode(BaseNode):
    type = "prompt"
    name = "Prompt"
    category = "Text"
    description = "多行 prompt，支持 {{var}} 模板变量渲染"
    inputs: list[PortDef] = []
    outputs = [PortDef(key="prompt", name="Prompt", type="PROMPT")]
    config_schema = [
        ConfigField(key="text", name="Text", type="textarea", default="",
                    placeholder="输入提示词，支持 {{var}} 变量", rows=6),
    ]

    async def execute(self, inputs, config, context):
        text = render_template(config.get("text", ""), context.variables)
        return {"prompt": text}


@register_node
class TextNode(BaseNode):
    type = "text"
    name = "Text"
    category = "Text"
    description = "纯文本"
    inputs: list[PortDef] = []
    outputs = [PortDef(key="text", name="Text", type="TEXT")]
    config_schema = [
        ConfigField(key="text", name="Text", type="textarea", default="", rows=4),
    ]

    async def execute(self, inputs, config, context):
        return {"text": config.get("text", "")}


@register_node
class CombinePromptNode(BaseNode):
    type = "combine_prompt"
    name = "Combine Prompt"
    category = "Text"
    description = "按模板把 character/scene/action/camera 组合成一个 prompt"
    inputs = [
        PortDef(key="character", name="Character", type="PROMPT", required=False),
        PortDef(key="scene", name="Scene", type="PROMPT", required=False),
        PortDef(key="action", name="Action", type="PROMPT", required=False),
        PortDef(key="camera", name="Camera", type="PROMPT", required=False),
    ]
    outputs = [PortDef(key="prompt", name="Prompt", type="PROMPT")]
    config_schema = [
        ConfigField(key="template", name="Template", type="textarea",
                    default="{{character}}\n{{scene}}\n{{action}}\n{{camera}}", rows=6),
    ]

    async def execute(self, inputs, config, context):
        variables = {k: v for k, v in (inputs or {}).items() if v}
        template = config.get("template") or "{{character}}\n{{scene}}\n{{action}}\n{{camera}}"
        text = render_template(template, variables)
        # collapse blank lines left by missing parts
        lines = [ln for ln in (ln.strip() for ln in text.splitlines()) if ln]
        return {"prompt": "\n".join(lines)}
