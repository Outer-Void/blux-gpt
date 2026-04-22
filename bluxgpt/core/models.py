from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ModelSpec:
    key: str            # canonical lane key (used for routing and user input)
    provider: str       # provider identifier: openai | deepseek | anthropic
    api_model_name: str # exact model name sent to the provider API
    description: str


MODEL_REGISTRY: Dict[str, ModelSpec] = {
    "gpt-5-mini": ModelSpec(
        key="gpt-5-mini",
        provider="openai",
        api_model_name="gpt-5-mini",
        description="Default balanced model (OpenAI)",
    ),
    "deepseek-chat": ModelSpec(
        key="deepseek-chat",
        provider="deepseek",
        api_model_name="deepseek-chat",
        description="Cheap non-thinking lane (DeepSeek)",
    ),
    "deepseek-reasoner": ModelSpec(
        key="deepseek-reasoner",
        provider="deepseek",
        api_model_name="deepseek-reasoner",
        description="Cheap reasoning lane (DeepSeek)",
    ),
    "claude-haiku-4.5": ModelSpec(
        key="claude-haiku-4.5",
        provider="anthropic",
        api_model_name="claude-haiku-4-5-20251001",
        description="Fast/light lane (Anthropic)",
    ),
}

# Alias keys that might come from user input
MODEL_ALIASES: Dict[str, str] = {
    "openai": "gpt-5-mini",
    "gpt": "gpt-5-mini",
    "deepseek": "deepseek-chat",
    "cheap": "deepseek-chat",
    "reasoner": "deepseek-reasoner",
    "reason": "deepseek-reasoner",
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
