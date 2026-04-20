from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ModelSpec:
    key: str
    provider: str
    env_model_name: str
    description: str


MODEL_REGISTRY: Dict[str, ModelSpec] = {
    "gpt-5-mini": ModelSpec(
        key="gpt-5-mini",
        provider="openai",
        env_model_name="OPENAI_MODEL",
        description="Default balanced model (OpenAI)",
    ),
    "deepseek-r2": ModelSpec(
        key="deepseek-r2",
        provider="deepseek",
        env_model_name="DEEPSEEK_MODEL",
        description="Cheap lane (DeepSeek)",
    ),
    "claude-haiku-4.5": ModelSpec(
        key="claude-haiku-4.5",
        provider="anthropic",
        env_model_name="ANTHROPIC_MODEL",
        description="Fast/light lane (Anthropic)",
    ),
}

# Alias keys that might come from user input
MODEL_ALIASES: Dict[str, str] = {
    "openai": "gpt-5-mini",
    "gpt": "gpt-5-mini",
    "deepseek": "deepseek-r2",
    "cheap": "deepseek-r2",
    "claude": "claude-haiku-4.5",
    "haiku": "claude-haiku-4.5",
    "fast": "claude-haiku-4.5",
}


def resolve_model(key: str) -> str:
    """Resolve a model key or alias to a canonical MODEL_REGISTRY key."""
    if key in MODEL_REGISTRY:
        return key
    if key in MODEL_ALIASES:
        return MODEL_ALIASES[key]
    raise ValueError(
        f"Unknown model: '{key}'. "
        f"Valid keys: {', '.join(MODEL_REGISTRY.keys())}. "
        f"Aliases: {', '.join(MODEL_ALIASES.keys())}."
    )
