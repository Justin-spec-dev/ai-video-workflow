"""Shared helpers for node implementations."""
from __future__ import annotations

import re

from .base import ConfigField

_VAR_RE = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")


def render_template(text: str, variables: dict) -> str:
    """Replace {{var}} placeholders; unknown vars render as empty string."""
    if not text:
        return ""
    return _VAR_RE.sub(lambda m: str(variables.get(m.group(1), "")), text)


def credential_field(kind: str) -> ConfigField:
    return ConfigField(key="credential_id", name="Credential", type="credential",
                       provider_kind=kind, default=None)


def llm_common_fields() -> list[ConfigField]:
    return [
        ConfigField(key="provider", name="Provider", type="select",
                    options=["openai_compatible"], default="openai_compatible"),
        credential_field("llm"),
        ConfigField(key="model", name="Model", type="model", default="deepseek-v4-flash"),
        ConfigField(key="base_url", name="Base URL", type="text", default=None,
                    placeholder="https://api.openai.com/v1"),
        ConfigField(key="temperature", name="Temperature", type="number",
                    default=0.7, min=0, max=2, step=0.1),
    ]


async def resolve_llm(context, config: dict):
    """Return (provider, credential) for an LLM-using node."""
    from ..providers import get_llm_provider

    provider = get_llm_provider(config.get("provider") or "openai_compatible")
    credential = await context.services.credentials.resolve(
        config.get("credential_id"), kind="llm", provider=config.get("provider") or "openai_compatible"
    )
    return provider, credential
