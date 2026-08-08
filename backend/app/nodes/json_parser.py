"""json_parser node (SPEC §5.2)."""
from __future__ import annotations

import json as _json

from ..workflow.context import NodeExecutionError
from .base import BaseNode, ConfigField, PortDef, register_node
from .jsonpath import JsonPathError, evaluate


@register_node
class JsonParserNode(BaseNode):
    type = "json_parser"
    name = "JSON Parser"
    category = "Utility"
    description = "用 jsonpath 子集从 JSON/文本中提取数据"
    inputs = [
        PortDef(key="json", name="JSON", type="JSON", required=False),
        PortDef(key="text", name="Text", type="TEXT", required=False),
    ]
    outputs = [
        PortDef(key="json", name="JSON", type="JSON"),
        PortDef(key="text", name="Text", type="TEXT"),
        PortDef(key="texts", name="Texts", type="TEXT[]"),
        PortDef(key="prompts", name="Prompts", type="PROMPT[]"),
    ]
    config_schema = [
        ConfigField(key="jsonpath", name="JSONPath", type="text", default="$",
                    placeholder="$.shots[*].prompt"),
    ]

    async def execute(self, inputs, config, context):
        data = inputs.get("json")
        if data is None and inputs.get("text") is not None:
            try:
                data = _json.loads(inputs["text"])
            except _json.JSONDecodeError as e:
                raise NodeExecutionError(f"输入 text 不是合法 JSON: {inputs['text'][:120]!r}") from e
        if data is None:
            raise NodeExecutionError("json_parser 需要 json 或 text 输入")

        path = (config.get("jsonpath") or "$").strip()
        try:
            matches = evaluate(data, path)
        except JsonPathError as e:
            raise NodeExecutionError(str(e)) from e

        if not matches:
            result = None
        elif len(matches) == 1:
            result = matches[0]
        else:
            result = matches

        flat_strings: list[str] = []
        for m in matches:
            if isinstance(m, str):
                flat_strings.append(m)
            elif isinstance(m, (int, float, bool)):
                flat_strings.append(str(m))
            else:
                flat_strings.append(_json.dumps(m, ensure_ascii=False))

        if isinstance(result, str):
            text_out = result
        elif result is None:
            text_out = ""
        else:
            text_out = _json.dumps(result, ensure_ascii=False)

        return {
            "json": result,
            "text": text_out,
            "texts": flat_strings,
            "prompts": flat_strings,
        }
