"""A fake provider over local HTTP: scripted responses, recorded requests."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from bluxgpt.config import Config

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_KEY = "sk-proj-FAKEFAKEFAKEFAKEFAKEFAKE1234"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeProvider:
    def __init__(self) -> None:
        self.script: list[tuple[int, dict[str, str], bytes]] = []
        self.requests: list[dict[str, Any]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def do_POST(self) -> None:
                length = int(self.headers.get("content-length", 0))
                outer.requests.append(
                    {
                        "path": self.path,
                        "headers": {k.lower(): v for k, v in self.headers.items()},
                        "body": json.loads(self.rfile.read(length) or b"{}"),
                    }
                )
                status, headers, body = (
                    outer.script.pop(0) if outer.script else (500, {}, b'{"error":{"message":"no script"}}')
                )
                if status == -1:  # hang until the client gives up
                    threading.Event().wait(float(headers.get("sleep", "5")))
                    return
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def reply(self, status: int, body: bytes | dict[str, Any], **headers: str) -> FakeProvider:
        raw = json.dumps(body).encode() if isinstance(body, dict) else body
        ctype = "text/event-stream" if raw.startswith((b"data:", b"event:")) else "application/json"
        self.script.append((status, {"content-type": ctype, **headers}, raw))
        return self

    def close(self) -> None:
        self.server.shutdown()


@pytest.fixture
def fake() -> Any:
    server = FakeProvider()
    yield server
    server.close()


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENAI_COMPATIBLE_API_KEY",
        "BLUXGPT_ROUTES",
        "BLUXGPT_DEFAULT_MODEL",
        "BLUXGPT_CONFIG",
        "DEEPSEEK_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    env.write_text(f"OPENAI_API_KEY={FAKE_KEY}\nANTHROPIC_API_KEY={FAKE_KEY}\nDEEPSEEK_API_KEY={FAKE_KEY}\n")
    monkeypatch.setenv("BLUXGPT_CONFIG", str(env))
    monkeypatch.setattr("bluxgpt.history.HISTORY_FILE", tmp_path / "history.jsonl")
    return Config.load()


def route(
    provider: str,
    model: str,
    *,
    base_url: str | None = None,
    route_id: str | None = None,
    caps: tuple[str, ...] = ("streaming", "tools", "structured_output"),
    tier: str = "primary",
    temperature: bool = True,
    seed: bool = False,
) -> dict[str, Any]:
    r = {
        "route_id": route_id or f"t.{provider}.{model}".replace("_", "-")[:60],
        "backend": "bluxgpt",
        "provider": provider,
        "provider_model": model,
        "locality": "remote",
        "tier": tier,
        "capabilities": list(caps),
        "determinism": {"temperature": temperature, "seed": seed},
    }
    if base_url:
        r["base_url"] = base_url
    return r


def request(model: str = "blux-main", prompt: str = "What is the capital of France?", **fields: Any) -> dict[str, Any]:
    return {
        "contract": "blux.model-request",
        "model_api_version": "1.0",
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        **fields,
    }
