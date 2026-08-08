"""Context nodes: variables / character_context / scene_context / style_context (SPEC §5.2)."""
from __future__ import annotations

from .base import BaseNode, ConfigField, PortDef, register_node


def _render_fields(config: dict, fields: list[tuple[str, str]]) -> str:
    """Render non-empty config fields as '标签: 值' lines."""
    lines = []
    for key, label in fields:
        value = (config.get(key) or "").strip() if isinstance(config.get(key), str) else config.get(key)
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


@register_node
class VariablesNode(BaseNode):
    type = "variables"
    name = "Variables"
    category = "Context"
    description = "key=value 列表，注入 context.variables 供 {{var}} 模板使用"
    provides_variables = True
    inputs: list[PortDef] = []
    outputs = [PortDef(key="text", name="Text", type="TEXT")]
    config_schema = [
        ConfigField(key="entries", name="Variables", type="textarea", rows=5, default="",
                    placeholder="character_name = Alice\ncity = Tokyo\nstyle = cinematic",
                    description='每行一个 key=value；也兼容 [{"key","value"}] JSON'),
    ]

    async def execute(self, inputs, config, context):
        entries = config.get("entries") or ""
        pairs: list[tuple[str, str]] = []
        if isinstance(entries, list):  # 旧格式：对象数组
            pairs = [(str(i.get("key", "")).strip(), str(i.get("value", "")))
                     for i in entries if isinstance(i, dict)]
        else:
            text = str(entries).strip()
            if text.startswith("["):  # 旧格式：JSON 字符串
                import json
                try:
                    for i in json.loads(text):
                        if isinstance(i, dict):
                            pairs.append((str(i.get("key", "")).strip(), str(i.get("value", ""))))
                except json.JSONDecodeError:
                    pass
            else:  # 新格式：每行 key=value
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    pairs.append((k.strip(), v.strip()))
        lines = []
        for key, value in pairs:
            if not key:
                continue
            context.variables[key] = value
            lines.append(f"{key}={value}")
        return {"text": "\n".join(lines)}


@register_node
class CharacterContextNode(BaseNode):
    type = "character_context"
    name = "Character Context"
    category = "Context"
    description = "角色一致性上下文（姓名/年龄/性别/外貌/发型/服装/性格/必须保持特征）"
    inputs: list[PortDef] = []
    outputs = [PortDef(key="prompt", name="Prompt", type="PROMPT")]
    config_schema = [
        ConfigField(key="name", name="姓名", type="text", default=""),
        ConfigField(key="age", name="年龄", type="text", default=""),
        ConfigField(key="gender", name="性别", type="text", default=""),
        ConfigField(key="appearance", name="外貌", type="textarea", default="", rows=3),
        ConfigField(key="hairstyle", name="发型", type="text", default=""),
        ConfigField(key="clothing", name="服装", type="textarea", default="", rows=2),
        ConfigField(key="personality", name="性格", type="text", default=""),
        ConfigField(key="must_keep", name="必须保持特征", type="textarea", default="", rows=2),
    ]

    async def execute(self, inputs, config, context):
        text = _render_fields(config, [
            ("name", "姓名"), ("age", "年龄"), ("gender", "性别"),
            ("appearance", "外貌"), ("hairstyle", "发型"), ("clothing", "服装"),
            ("personality", "性格"), ("must_keep", "必须保持特征"),
        ])
        return {"prompt": text}


@register_node
class SceneContextNode(BaseNode):
    type = "scene_context"
    name = "Scene Context"
    category = "Context"
    description = "场景上下文（地点/时间/天气/环境/空间布局/持续物体）"
    inputs: list[PortDef] = []
    outputs = [PortDef(key="prompt", name="Prompt", type="PROMPT")]
    config_schema = [
        ConfigField(key="location", name="地点", type="text", default=""),
        ConfigField(key="time", name="时间", type="text", default=""),
        ConfigField(key="weather", name="天气", type="text", default=""),
        ConfigField(key="environment", name="环境", type="textarea", default="", rows=3),
        ConfigField(key="layout", name="空间布局", type="textarea", default="", rows=2),
        ConfigField(key="persistent_objects", name="持续物体", type="textarea", default="", rows=2),
    ]

    async def execute(self, inputs, config, context):
        text = _render_fields(config, [
            ("location", "地点"), ("time", "时间"), ("weather", "天气"),
            ("environment", "环境"), ("layout", "空间布局"), ("persistent_objects", "持续物体"),
        ])
        return {"prompt": text}


@register_node
class StyleContextNode(BaseNode):
    type = "style_context"
    name = "Style Context"
    category = "Context"
    description = "风格上下文（画面风格/镜头语言/调色/光线/宽高比/胶片感）"
    inputs: list[PortDef] = []
    outputs = [PortDef(key="prompt", name="Prompt", type="PROMPT")]
    config_schema = [
        ConfigField(key="visual_style", name="画面风格", type="text", default=""),
        ConfigField(key="camera_language", name="镜头语言", type="text", default=""),
        ConfigField(key="color_grading", name="调色", type="text", default=""),
        ConfigField(key="lighting", name="光线", type="text", default=""),
        ConfigField(key="aspect_ratio", name="宽高比", type="text", default=""),
        ConfigField(key="film_texture", name="胶片感", type="text", default=""),
    ]

    async def execute(self, inputs, config, context):
        text = _render_fields(config, [
            ("visual_style", "画面风格"), ("camera_language", "镜头语言"),
            ("color_grading", "调色"), ("lighting", "光线"),
            ("aspect_ratio", "宽高比"), ("film_texture", "胶片感"),
        ])
        return {"prompt": text}
