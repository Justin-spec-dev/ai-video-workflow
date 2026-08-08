"""test_nodes.py: prompt 模板渲染、combine_prompt、context 节点、json_parser、variables (SPEC §11)."""
import pytest

from app.nodes.ai import StoryboardNode
from app.nodes.context_nodes import (CharacterContextNode, SceneContextNode,
                                     StyleContextNode, VariablesNode)
from app.nodes.json_parser import JsonParserNode
from app.nodes.text import CombinePromptNode, PromptNode
from app.workflow.context import ExecutionContext, NodeExecutionError


def make_context(variables=None) -> ExecutionContext:
    return ExecutionContext(workflow_id="wf", run_id="run", variables=variables or {})


async def test_prompt_template_rendering():
    ctx = make_context({"character": "a young witch", "scene": "rainy tokyo"})
    out = await PromptNode().execute({}, {"text": "{{character}} walks through {{scene}}"}, ctx)
    assert out["prompt"] == "a young witch walks through rainy tokyo"


async def test_prompt_unknown_var_renders_empty():
    out = await PromptNode().execute({}, {"text": "hi {{missing}}!"}, make_context())
    assert out["prompt"] == "hi !"


async def test_combine_prompt():
    inputs = {"character": "骑士", "action": "骑马穿过森林"}
    out = await CombinePromptNode().execute(
        inputs, {"template": "{{character}} {{action}} {{camera}}"}, make_context())
    assert out["prompt"] == "骑士 骑马穿过森林"  # 缺失的 camera 被折叠
    assert "{{" not in out["prompt"]


async def test_character_context():
    out = await CharacterContextNode().execute(
        {}, {"name": "Aria", "age": "25", "appearance": "silver hair"}, make_context())
    assert "姓名: Aria" in out["prompt"]
    assert "年龄: 25" in out["prompt"]
    assert "外貌: silver hair" in out["prompt"]
    assert "服装" not in out["prompt"]  # 空字段不输出


async def test_scene_and_style_context():
    s = await SceneContextNode().execute({}, {"location": "海边", "weather": "暴风雨"}, make_context())
    assert "地点: 海边" in s["prompt"] and "天气: 暴风雨" in s["prompt"]
    st = await StyleContextNode().execute({}, {"visual_style": "赛博朋克"}, make_context())
    assert st["prompt"] == "画面风格: 赛博朋克"


async def test_variables_injects_context():
    ctx = make_context()
    out = await VariablesNode().execute(
        {}, {"entries": "hero = Aria\nplace = Neo Tokyo"}, ctx)
    assert ctx.variables == {"hero": "Aria", "place": "Neo Tokyo"}
    assert "hero=Aria" in out["text"]
    # 下游 prompt 节点可以使用注入的变量
    p = await PromptNode().execute({}, {"text": "{{hero}} in {{place}}"}, ctx)
    assert p["prompt"] == "Aria in Neo Tokyo"


SHOTS_JSON = {
    "shots": [
        {"shot_id": "s1", "title": "开场", "prompt": "wide shot of city"},
        {"shot_id": "s2", "title": "追逐", "prompt": "close-up chase"},
    ]
}


async def test_json_parser_wildcard_path():
    out = await JsonParserNode().execute(
        {"json": SHOTS_JSON}, {"jsonpath": "$.shots[*].prompt"}, make_context())
    assert out["prompts"] == ["wide shot of city", "close-up chase"]
    assert out["texts"] == ["wide shot of city", "close-up chase"]
    assert out["json"] == ["wide shot of city", "close-up chase"]


async def test_json_parser_field_and_index():
    out = await JsonParserNode().execute(
        {"json": SHOTS_JSON}, {"jsonpath": "$.shots[1].title"}, make_context())
    assert out["json"] == "追逐"
    assert out["text"] == "追逐"


async def test_json_parser_recursive_descent():
    out = await JsonParserNode().execute(
        {"json": SHOTS_JSON}, {"jsonpath": "$..prompt"}, make_context())
    assert out["prompts"] == ["wide shot of city", "close-up chase"]


async def test_json_parser_text_input():
    import json
    out = await JsonParserNode().execute(
        {"text": json.dumps(SHOTS_JSON)}, {"jsonpath": "$.shots[0].shot_id"}, make_context())
    assert out["text"] == "s1"


async def test_json_parser_bad_path_errors():
    with pytest.raises(NodeExecutionError):
        await JsonParserNode().execute({"json": {}}, {"jsonpath": "shots[*]"}, make_context())


async def test_storyboard_parse_failure_raises_not_crashes(mocker):
    """LLM 输出解析失败要报错而非崩溃 (SPEC §5.2)."""
    node = StoryboardNode()
    # resolve_llm 被 ai.py 以名字导入，patch ai 模块命名空间
    provider = mocker.AsyncMock()
    provider.generate = mocker.AsyncMock(return_value="这不是 JSON，只是一段话")
    mocker.patch("app.nodes.ai.resolve_llm", new=mocker.AsyncMock(return_value=(provider, None)))
    with pytest.raises(NodeExecutionError, match="无法解析"):
        await node.execute({"story": "一个故事"}, {}, make_context())


async def test_variables_legacy_json_still_works():
    """旧的 JSON 数组格式保持兼容。"""
    ctx = make_context()
    out = await VariablesNode().execute(
        {}, {"entries": [{"key": "hero", "value": "Aria"}]}, ctx)
    assert ctx.variables == {"hero": "Aria"}
    assert "hero=Aria" in out["text"]
