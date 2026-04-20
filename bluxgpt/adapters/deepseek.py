from __future__ import annotations

from openai import OpenAI

from bluxgpt.adapters.base import BaseAdapter


class DeepSeekAdapter(BaseAdapter):
    """Adapter for DeepSeek models.

    DeepSeek exposes an OpenAI-compatible endpoint but uses the Chat
    Completions API — NOT the newer OpenAI Responses API.  Using
    client.responses.create() against DeepSeek will 404.
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def complete(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        return (content or "").strip()
