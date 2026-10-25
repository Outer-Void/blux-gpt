"""The mock provider: deterministic, offline, and able to fail on purpose (tests, CI, demos).

The route's `provider_model` selects the behaviour:

| model | does |
|---|---|
| `echo` | answers "echo: <last user message>" |
| `json` | returns a minimal instance of the requested JSON Schema |
| `tool` | calls the first declared tool with minimal arguments |
| `badjson` | returns text that does not match the requested schema |
| `badtool` | calls a tool that was never declared |
| `fail-<code>` | fails with that Model API error code, e.g. `fail-provider_unavailable` |
| `leak` | fails with a message that contains a fake credential (to prove scrubbing) |
| `slow-<ms>` | waits, then echoes (timeouts and cancellation) |

Everything a mock says is labelled `provider: mock` in the response: mocked results are never presented
as real provider results.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from typing import Any

from bluxgpt.api import ModelError, response, usage
from bluxgpt.transport import Transport

FAKE_SECRET = "sk-proj-MOCKMOCKMOCKMOCKMOCKMOCKMOCK0000"  # noqa: S105 - deliberately fake, proves scrubbing


def minimal(schema: dict[str, Any]) -> Any:
    """A small instance of a JSON Schema (enough for the schemas tests and demos use)."""
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), kind[0])
    if kind == "object":
        props = schema.get("properties") or {}
        return {k: minimal(props.get(k, {})) for k in schema.get("required", list(props))}
    if kind == "array":
        return [minimal(schema.get("items") or {})] * max(1, schema.get("minItems", 1))
    if kind == "integer":
        return int(schema.get("minimum", 1))
    if kind == "number":
        return float(schema.get("minimum", 1))
    if kind == "boolean":
        return True
    if kind == "null":
        return None
    return "x" * max(1, schema.get("minLength", 1))


class Mock:
    name = "mock"

    def generate(
        self,
        request: dict[str, Any],
        route: dict[str, Any],
        *,
        config: Any,
        transport: Transport,
        deadline: float,
        cancel: threading.Event,
        emit: Callable[[str, dict[str, Any]], None],
    ) -> dict[str, Any]:
        started = time.monotonic()
        model = route["provider_model"]

        def fail(code: str, msg: str) -> ModelError:
            return ModelError(code, msg, provider=route["provider"], route_id=route["route_id"])

        if model.startswith("fail-"):
            code = model[len("fail-") :].upper()
            raise fail(code, f"mock failure {code}")
        if model == "leak":
            raise fail(
                "PROVIDER_ERROR", f"upstream said: invalid key {FAKE_SECRET} (Authorization: Bearer {FAKE_SECRET})"
            )
        if model.startswith("slow-"):
            end = started + int(model[len("slow-") :]) / 1000
            while time.monotonic() < end:
                if cancel.is_set():
                    raise fail("CANCELLED", "Cancelled by the caller.")
                if time.monotonic() >= deadline:
                    raise fail("PROVIDER_TIMEOUT", "The provider did not answer before the deadline.")
                time.sleep(0.01)
        last = next((m["content"] for m in reversed(request["messages"]) if m["role"] == "user"), "")
        fmt = request.get("response_format") or {}
        text: str | None = f"echo: {last}"
        json_value = None
        calls: list[dict[str, Any]] = []
        finish = "stop"
        if fmt.get("type") == "json_schema":
            json_value = minimal(fmt["schema"]) if model != "badjson" else {"unexpected": True}
            text = None
        if model == "tool" and request.get("tools"):
            tool = request["tools"][0]
            calls, text, finish = (
                [{"id": "call_mock_1", "name": tool["name"], "arguments": minimal(tool["input_schema"])}],
                None,
                "tool_calls",
            )
        if model == "badtool":
            calls, text, finish = (
                [{"id": "call_mock_1", "name": "undeclared_tool", "arguments": {}}],
                None,
                "tool_calls",
            )
        first = None
        if request.get("stream") and text:
            for i, word in enumerate(text.split(" ")):
                if first is None:
                    first = int((time.monotonic() - started) * 1000)
                emit("delta", {"text": word if i == 0 else " " + word})
        for call in calls:
            emit("tool_call", call)
        words = len(last.split())
        use = usage(words + 3, len((text or "").split()) + len(calls) * 5)
        if request.get("stream"):
            emit("usage", use)
        return response(
            request,
            route,
            text=text,
            json_value=json_value,
            tool_calls=calls,
            finish_reason=finish,
            usage_doc=use,
            request_id="mock-" + hashlib.sha256(last.encode()).hexdigest()[:12],
            latency_ms=int((time.monotonic() - started) * 1000),
            first_token_ms=first,
            retries=0,
        )
