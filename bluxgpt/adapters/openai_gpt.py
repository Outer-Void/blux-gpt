from __future__ import annotations

from openai import OpenAI

from bluxgpt.adapters.base import BaseAdapter


class OpenAIGPTAdapter(BaseAdapter):
    """Adapter for OpenAI models using the Responses API."""

    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def complete(self, prompt: str) -> str:
        # OpenAI Responses API (introduced 2025)
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )
        return response.output_text.strip()
