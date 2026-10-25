"""REAL provider acceptance: talks to the actual provider APIs and spends a few tokens.

Runs only with BLUXGPT_REAL_PROVIDERS=1 and the provider's key configured. Each route gets one tiny prompt.
Results are REAL; nothing here is mocked. An account without balance is reported as a skip with the
normalized reason, not as a pass.
"""

from __future__ import annotations

import os
import threading
import time

import pytest

from bluxgpt import client
from bluxgpt.api import ModelError
from bluxgpt.config import Config
from bluxgpt.gateway import Gateway

pytestmark = pytest.mark.real
if os.environ.get("BLUXGPT_REAL_PROVIDERS") != "1":
    pytest.skip("real providers: set BLUXGPT_REAL_PROVIDERS=1 (uses credit)", allow_module_level=True)

CONFIG = Config.load()
ROUTES = {
    (r["provider"], r["provider_model"]): r for m in client.load_routes(CONFIG)["models"].values() for r in m["routes"]
}
KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}


@pytest.mark.parametrize("key", sorted(ROUTES), ids=lambda k: f"{k[0]}/{k[1]}")
def test_real_route(key: tuple[str, str]) -> None:
    route = ROUTES[key]
    if not CONFIG.secret(KEYS[route["provider"]]):
        pytest.skip(f"{KEYS[route['provider']]} not configured")
    req = {
        "contract": "blux.model-request",
        "model_api_version": "1.0",
        "model": "blux-main",
        "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
        "generation": {"max_output_tokens": 400},
    }
    try:
        resp = Gateway(CONFIG).generate(
            req, route, deadline=time.monotonic() + 90, cancel=threading.Event(), emit=lambda k, d: None
        )
    except ModelError as exc:
        if exc.code in ("PROVIDER_QUOTA_EXCEEDED", "PROVIDER_AUTH_FAILED"):
            pytest.skip(f"REAL {route['route_id']}: {exc.code} ({exc.message[:80]})")
        raise
    assert resp["provider"]["provider"] == route["provider"] and resp["usage"]["reported_by_provider"]
    assert resp["output"]["text"]
