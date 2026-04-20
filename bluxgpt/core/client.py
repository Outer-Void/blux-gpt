from __future__ import annotations

from bluxgpt.adapters.base import BaseAdapter
from bluxgpt.adapters.claude import ClaudeAdapter
from bluxgpt.adapters.deepseek import DeepSeekAdapter
from bluxgpt.adapters.openai_gpt import OpenAIGPTAdapter
from bluxgpt.core.config import Settings
from bluxgpt.core.models import MODEL_REGISTRY, resolve_model


class BluxClient:
    """Unified multi-model client.

    Resolves a model key to its provider, validates the required API key
    is present, and returns the appropriate adapter.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _adapter_for(self, model_key: str) -> BaseAdapter:
        canonical = resolve_model(model_key)
        spec = MODEL_REGISTRY[canonical]

        if spec.provider == "openai":
            if not self.settings.openai_api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not set. "
                    "Add it to ~/.config/bluxgpt/.env"
                )
            return OpenAIGPTAdapter(
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
            )

        if spec.provider == "deepseek":
            if not self.settings.deepseek_api_key:
                raise RuntimeError(
                    "DEEPSEEK_API_KEY is not set. "
                    "Add it to ~/.config/bluxgpt/.env"
                )
            return DeepSeekAdapter(
                api_key=self.settings.deepseek_api_key,
                base_url=self.settings.deepseek_base_url,
                model=self.settings.deepseek_model,
            )

        if spec.provider == "anthropic":
            if not self.settings.anthropic_api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. "
                    "Add it to ~/.config/bluxgpt/.env"
                )
            return ClaudeAdapter(
                api_key=self.settings.anthropic_api_key,
                model=self.settings.anthropic_model,
            )

        raise RuntimeError(f"Unsupported provider: {spec.provider!r}")

    def complete(self, prompt: str, model_key: str) -> str:
        adapter = self._adapter_for(model_key)
        return adapter.complete(prompt)

    def test_model(self, model_key: str) -> bool:
        """Return True if the model API responds to a connectivity ping."""
        try:
            adapter = self._adapter_for(model_key)
            return adapter.test_connectivity()
        except RuntimeError:
            # API key missing — not a connectivity failure, just not configured
            return False
        except Exception:
            return False
