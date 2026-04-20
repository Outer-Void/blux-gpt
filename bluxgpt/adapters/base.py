from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    """Abstract base for all BluxGPT model adapters."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Send a prompt and return the full response as a string."""
        raise NotImplementedError

    def test_connectivity(self) -> bool:
        """Quick connectivity test. Returns True if the API responds."""
        try:
            result = self.complete("Say 'ok' and nothing else.")
            return bool(result)
        except Exception:
            return False
