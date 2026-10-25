"""Provider implementations. Each turns a Model API request into a normalized response for one route."""

from __future__ import annotations

from typing import Any

from bluxgpt.providers.anthropic import Anthropic
from bluxgpt.providers.mock import Mock
from bluxgpt.providers.openai_compat import OpenAICompatible

PROVIDERS: dict[str, Any] = {
    "openai": OpenAICompatible(
        "openai", base_url="https://api.openai.com/v1", key_name="OPENAI_API_KEY", flavor="openai"
    ),
    "deepseek": OpenAICompatible(
        "deepseek", base_url="https://api.deepseek.com", key_name="DEEPSEEK_API_KEY", flavor="deepseek"
    ),
    # Any OpenAI-compatible server (llama.cpp's llama-server, vLLM, Ollama's /v1 ...); base_url comes from the route.
    "openai-compatible": OpenAICompatible(
        "openai-compatible", base_url=None, key_name="OPENAI_COMPATIBLE_API_KEY", flavor="generic"
    ),
    "anthropic": Anthropic(),
    "mock": Mock(),
}
