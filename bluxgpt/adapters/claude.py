from __future__ import annotations

from anthropic import Anthropic

from bluxgpt.adapters.base import BaseAdapter


class ClaudeAdapter(BaseAdapter):
    """Adapter for Anthropic Claude models."""

    def __init__(self, api_key: str, model: str) -> None:
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def complete(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = []
        for block in response.content:
            text = getattr(block, "text", "")
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
