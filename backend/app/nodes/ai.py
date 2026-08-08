"""AI nodes: llm / prompt_optimizer / storyboard (SPEC §5.2)."""
from __future__ import annotations

import json
import re

from ..workflow.context import NodeExecutionError
from .base import BaseNode, ConfigField, PortDef, register_node
from .common import credential_field, llm_common_fields, resolve_llm


def _try_parse_json(text: str):
    """Try to parse LLM output as JSON (tolerating ```json fences). Returns None on failure."""
    if not text:
        return None
    candidates = [text.strip()]
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        candidates.insert(0, m.group(1).strip())
    for c in candidates:
        try:
            return json.loads(c)
        except (json.JSONDecodeError, TypeError):
            continue
    # last resort: first {...} or [...] block
    m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


@register_node
class LLMNode(BaseNode):
    type = "llm"
    name = "LLM"
    category = "AI"
    description = "OpenAI 兼容 chat completions"
    inputs = [
        PortDef(key="system_prompt", name="System Prompt", type="TEXT", required=False),
        PortDef(key="prompt", name="Prompt", type="TEXT", required=True),
        PortDef(key="context", name="Context", type="TEXT", required=False),
    ]
    outputs = [
        PortDef(key="text", name="Text", type="TEXT"),
        PortDef(key="json", name="JSON", type="JSON"),
    ]
    config_schema = llm_common_fields() + [
        ConfigField(key="system_prompt", name="System Prompt", type="textarea", default="", rows=4),
        ConfigField(key="max_tokens", name="Max Tokens", type="number", default=None, min=1, step=1),
    ]

    async def execute(self, inputs, config, context):
        if not (inputs.get("prompt") or "").strip():
            raise NodeExecutionError("输入为空：请连接并填写上游文本/Prompt 节点后再运行")
        provider, credential = await resolve_llm(context, config)
        system = inputs.get("system_prompt") or config.get("system_prompt") or None
        text = await provider.generate(
            system=system,
            prompt=inputs.get("prompt") or "",
            context=inputs.get("context"),
            model=config.get("model"),
            temperature=config.get("temperature"),
            max_tokens=config.get("max_tokens"),
            credential=credential,
            base_url=config.get("base_url") or None,
        )
        return {"text": text, "json": _try_parse_json(text)}


_MODE_PROMPTS = {
    "optimize": "You are a prompt engineer for AI video generation. Optimize the user's prompt to be vivid, cinematic and precise. Return ONLY the optimized prompt text.",
    "expand": "You are a prompt engineer for AI video generation. Expand the user's prompt with rich visual detail (subject, motion, environment, lighting, camera). Return ONLY the expanded prompt text.",
    "structured": "You are a prompt engineer for AI video generation. Rewrite the user's prompt in a structured form: Subject / Action / Scene / Camera / Lighting / Style. Return ONLY the structured prompt text.",
    "rewrite": "You are a prompt rewriter. Rewrite the user's prompt exactly according to the rewrite instruction. Return ONLY the rewritten prompt text.",
}

_TARGET_HINTS = {
    "generic": "",
    "minimax_h3": "Target model: MiniMax H3. Prefer natural-language descriptive prompts, include camera movement and subject motion.",
    "kling": "Target model: Kling. Emphasize subject + motion + scene, keep it concise.",
    "veo": "Target model: Veo. Use cinematic terminology, describe shots and audio cues.",
    "seedance": "Target model: Seedance. Describe motion trajectory and camera language precisely.",
}


@register_node
class PromptOptimizerNode(BaseNode):
    type = "prompt_optimizer"
    name = "Prompt Optimizer"
    category = "AI"
    description = "用 LLM 优化视频生成 prompt；Review 编辑后直接使用 edited_prompt"
    inputs = [
        PortDef(key="prompt", name="Prompt", type="PROMPT", required=True),
        PortDef(key="character", name="Character", type="PROMPT", required=False),
        PortDef(key="scene", name="Scene", type="PROMPT", required=False),
        PortDef(key="style", name="Style", type="PROMPT", required=False),
    ]
    outputs = [
        PortDef(key="prompt", name="Prompt", type="PROMPT"),
        PortDef(key="original", name="Original", type="PROMPT"),
    ]
    config_schema = [
        ConfigField(key="mode", name="Mode", type="select",
                    options=["optimize", "expand", "structured", "rewrite"], default="optimize"),
        ConfigField(key="rewrite_instruction", name="Rewrite Instruction", type="textarea", default="", rows=3),
        ConfigField(key="target_video_model", name="Target Video Model", type="select",
                    options=["generic", "minimax_h3", "kling", "veo", "seedance"], default="generic"),
        *llm_common_fields(),
        ConfigField(key="system_prompt", name="System Prompt", type="textarea", default="", rows=4,
                    description="留空则按 mode 使用内置 system prompt"),
        ConfigField(key="edited_prompt", name="Edited Prompt (Review)", type="textarea", default="", rows=4,
                    description="非空时跳过 LLM，直接输出该文本"),
    ]

    async def execute(self, inputs, config, context):
        original = (inputs.get("prompt") or "").strip()
        if not original:
            raise NodeExecutionError("提示词为空：请在上游 Prompt 节点填写内容后再运行")
        edited = (config.get("edited_prompt") or "").strip()
        if edited:
            await context.log("使用 Review 中编辑后的 prompt（跳过 LLM）")
            return {"prompt": edited, "original": original}

        provider, credential = await resolve_llm(context, config)
        mode = config.get("mode") or "optimize"
        system = (config.get("system_prompt") or "").strip() or _MODE_PROMPTS.get(mode, _MODE_PROMPTS["optimize"])
        if mode == "rewrite" and config.get("rewrite_instruction"):
            system += f"\nRewrite instruction: {config['rewrite_instruction']}"
        hint = _TARGET_HINTS.get(config.get("target_video_model") or "generic", "")
        if hint:
            system += f"\n{hint}"

        context_parts = [p for p in (inputs.get("character"), inputs.get("scene"), inputs.get("style")) if p]
        optimized = await provider.generate(
            system=system,
            prompt=original,
            context="\n\n".join(context_parts) or None,
            model=config.get("model"),
            temperature=config.get("temperature"),
            max_tokens=None,
            credential=credential,
            base_url=config.get("base_url") or None,
        )
        return {"prompt": optimized.strip(), "original": original}


_STORYBOARD_SYSTEM = """You are a film director creating a storyboard. Break the user's story into shots.
Return STRICT JSON only (no markdown fences), an object {"shots": [...]} where each shot is:
{"shot_id": "shot_1", "title": "...", "prompt": "detailed video generation prompt for this shot"}.
Keep prompts self-contained and cinematic."""


@register_node
class StoryboardNode(BaseNode):
    type = "storyboard"
    name = "Storyboard"
    category = "AI"
    description = "用 LLM 把故事拆成 shots JSON"
    inputs = [
        PortDef(key="story", name="Story", type="TEXT", required=True),
    ]
    outputs = [
        PortDef(key="json", name="JSON", type="JSON"),
        PortDef(key="prompts", name="Prompts", type="PROMPT[]"),
        PortDef(key="texts", name="Texts", type="TEXT[]"),
    ]
    config_schema = llm_common_fields() + [
        ConfigField(key="shot_count", name="Shot Count", type="number", default=None, min=1, step=1),
    ]

    async def execute(self, inputs, config, context):
        provider, credential = await resolve_llm(context, config)
        system = _STORYBOARD_SYSTEM
        if config.get("shot_count"):
            system += f"\nCreate exactly {int(config['shot_count'])} shots."
        text = await provider.generate(
            system=system,
            prompt=inputs.get("story") or "",
            context=None,
            model=config.get("model"),
            temperature=config.get("temperature"),
            max_tokens=None,
            credential=credential,
            base_url=config.get("base_url") or None,
        )
        parsed = _try_parse_json(text)
        shots = None
        if isinstance(parsed, dict) and isinstance(parsed.get("shots"), list):
            shots = parsed["shots"]
        elif isinstance(parsed, list):
            shots = parsed
        if shots is None:
            raise NodeExecutionError(
                f"LLM 输出无法解析为 shots JSON（前 200 字符）: {text[:200]!r}"
            )
        prompts = [str(s.get("prompt", "")) for s in shots if isinstance(s, dict)]
        texts = [str(s.get("title") or s.get("shot_id") or f"shot_{i+1}")
                 for i, s in enumerate(shots) if isinstance(s, dict)]
        return {"json": {"shots": shots}, "prompts": prompts, "texts": texts}
