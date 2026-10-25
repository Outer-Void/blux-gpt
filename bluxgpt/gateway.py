"""The gateway: run one Model API request on one route, with the right provider and transport."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from bluxgpt.api import ModelError
from bluxgpt.config import SECRET_NAMES, Config
from bluxgpt.providers import PROVIDERS
from bluxgpt.transport import Transport

Emit = Callable[[str, dict[str, Any]], None]


class Gateway:
    def __init__(self, config: Config | None = None, *, transport_factory: Callable[[], Transport] = Transport) -> None:
        self.config = config or Config.load()
        self.transport_factory = transport_factory

    def secrets(self) -> tuple[str, ...]:
        return tuple(v for v in (self.config.secret(n) for n in SECRET_NAMES) if v)

    def generate(
        self, request: dict[str, Any], route: dict[str, Any], *, deadline: float, cancel: threading.Event, emit: Emit
    ) -> dict[str, Any]:
        provider = PROVIDERS.get(route.get("provider", ""))
        if provider is None:
            raise ModelError(
                "PROVIDER_NOT_CONFIGURED",
                f"BluxGPT has no provider {route.get('provider')!r}.",
                provider=route.get("provider"),
                route_id=route.get("route_id"),
            )
        if route["provider"] == "deepseek" and self.config.get("DEEPSEEK_BASE_URL") and not route.get("base_url"):
            route = {**route, "base_url": self.config.get("DEEPSEEK_BASE_URL")}
        transport = self.transport_factory()
        try:
            result: dict[str, Any] = provider.generate(
                request, route, config=self.config, transport=transport, deadline=deadline, cancel=cancel, emit=emit
            )
            return result
        except ModelError as exc:
            exc.message = _scrub(exc.message, self.secrets())
            exc.details.setdefault("retries", transport.retries)
            raise
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ModelError(
                "PROVIDER_ERROR",
                f"Unexpected provider response ({type(exc).__name__}).",
                provider=route["provider"],
                route_id=route["route_id"],
                details={"retries": transport.retries},
            ) from None


def _scrub(text: str, secrets: tuple[str, ...]) -> str:
    from bluxgpt.api import scrub

    return scrub(text, secrets)
