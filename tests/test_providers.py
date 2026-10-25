"""Providers and transport against local HTTP fixtures (MOCKED: no real provider is contacted)."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest

from bluxgpt.api import ModelError
from bluxgpt.config import Config
from bluxgpt.gateway import Gateway
from bluxgpt.transport import Transport
from tests.conftest import FAKE_KEY, FakeProvider, fixture, request, route


def run(
    config: Config, req: dict[str, Any], rt: dict[str, Any], *, timeout: float = 10, retries: int = 2
) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    gw = Gateway(config, transport_factory=lambda: Transport(max_retries=retries, backoff_s=0.01))
    resp = gw.generate(
        req, rt, deadline=time.monotonic() + timeout, cancel=threading.Event(), emit=lambda k, d: events.append((k, d))
    )
    return resp, events


def fail(config: Config, req: dict[str, Any], rt: dict[str, Any], **kw: Any) -> ModelError:
    with pytest.raises(ModelError) as info:
        run(config, req, rt, **kw)
    return info.value


# OpenAI ---------------------------------------------------------------------------------------------------


def test_openai_chat_is_normalized(config: Config, fake: FakeProvider) -> None:
    fake.reply(200, fixture("openai_chat.json"))
    resp, _ = run(config, request(system="Be brief."), route("openai", "gpt-5-mini", base_url=fake.url))
    assert resp["output"]["text"] == "Paris." and resp["status"] == "completed" and resp["finish_reason"] == "stop"
    assert resp["usage"] == {
        "input_tokens": 12,
        "output_tokens": 2,
        "total_tokens": 14,
        "reasoning_tokens": 0,
        "cached_input_tokens": 0,
        "reported_by_provider": True,
    }
    assert resp["provider"] == {
        "backend": "bluxgpt",
        "provider": "openai",
        "provider_model": "gpt-5-mini",
        "route_id": "t.openai.gpt-5-mini",
        "locality": "remote",
        "request_id": "chatcmpl-fixture-1",
    }
    sent = fake.requests[0]
    assert sent["path"] == "/v1/chat/completions" and sent["headers"]["authorization"] == f"Bearer {FAKE_KEY}"
    assert sent["body"]["messages"][0] == {"role": "system", "content": "Be brief."}
    assert FAKE_KEY not in json.dumps(sent["body"]) and FAKE_KEY not in json.dumps(resp)


def test_openai_structured_output_and_tokens(config: Config, fake: FakeProvider) -> None:
    body = json.loads(fixture("openai_chat.json"))
    body["choices"][0]["message"]["content"] = '{"answer": "Paris"}'
    fake.reply(200, body)
    schema = {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}
    resp, _ = run(
        config,
        request(
            response_format={"type": "json_schema", "name": "city", "schema": schema},
            generation={"max_output_tokens": 50},
        ),
        route("openai", "gpt-5-mini", base_url=fake.url),
    )
    assert resp["output"]["json"] == {"answer": "Paris"}
    sent = fake.requests[0]["body"]
    assert (
        sent["response_format"]["type"] == "json_schema" and sent["response_format"]["json_schema"]["schema"] == schema
    )
    assert sent["max_completion_tokens"] == 50 and "max_tokens" not in sent


def test_openai_tool_calls_are_returned_never_run(config: Config, fake: FakeProvider) -> None:
    fake.reply(200, fixture("openai_tool.json"))
    tools = [{"name": "get_weather", "description": "w", "input_schema": {"type": "object"}}]
    resp, _ = run(config, request(tools=tools), route("openai", "gpt-5-mini", base_url=fake.url))
    assert resp["status"] == "tool_calls"
    assert resp["output"]["tool_calls"] == [{"id": "call_1", "name": "get_weather", "arguments": {"city": "Paris"}}]
    assert fake.requests[0]["body"]["tools"][0]["function"]["name"] == "get_weather"


def test_openai_streaming(config: Config, fake: FakeProvider) -> None:
    fake.reply(200, fixture("openai_stream.sse"))
    resp, events = run(config, request(stream=True), route("openai", "gpt-5-mini", base_url=fake.url))
    assert [d["text"] for k, d in events if k == "delta"] == ["Hel", "lo"]
    assert resp["output"]["text"] == "Hello" and resp["usage"]["total_tokens"] == 7
    assert resp["timing"]["first_token_ms"] is not None
    assert fake.requests[0]["body"]["stream_options"] == {"include_usage": True}


def test_deepseek_reasoning_text_is_dropped(config: Config, fake: FakeProvider) -> None:
    fake.reply(200, fixture("deepseek_reasoner.json"))
    resp, _ = run(config, request(model="blux-reason"), route("deepseek", "deepseek-reasoner", base_url=fake.url))
    assert "PRIVATE REASONING" not in json.dumps(resp)
    assert resp["output"]["text"] == "42" and resp["usage"]["reasoning_tokens"] == 38
    assert resp["usage"]["cached_input_tokens"] == 3


def test_deepseek_json_mode_and_max_tokens(config: Config, fake: FakeProvider) -> None:
    body = json.loads(fixture("deepseek_reasoner.json"))
    body["choices"][0]["message"]["content"] = '```json\n{"ok": true}\n```'
    fake.reply(200, body)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    resp, _ = run(
        config,
        request(
            response_format={"type": "json_schema", "name": "x", "schema": schema}, generation={"max_output_tokens": 9}
        ),
        route("deepseek", "deepseek-chat", base_url=fake.url),
    )
    sent = fake.requests[0]["body"]
    assert sent["response_format"] == {"type": "json_object"} and sent["max_tokens"] == 9
    assert "JSON Schema" in sent["messages"][0]["content"]
    assert resp["output"]["json"] == {"ok": True}


# Anthropic ------------------------------------------------------------------------------------------------


def test_anthropic_message_drops_thinking(config: Config, fake: FakeProvider) -> None:
    fake.reply(200, fixture("anthropic_message.json"))
    req = request(model="blux-fast", system="Reply in French.", context=[{"kind": "note", "content": "be polite"}])
    resp, _ = run(config, req, route("anthropic", "claude-haiku-4-5-20251001", base_url=fake.url))
    assert resp["output"]["text"] == "Bonjour." and "PRIVATE THINKING" not in json.dumps(resp)
    sent = fake.requests[0]
    assert sent["headers"]["x-api-key"] == FAKE_KEY and sent["headers"]["anthropic-version"] == "2023-06-01"
    assert sent["body"]["system"].startswith("Reply in French.") and "be polite" in sent["body"]["system"]


def test_anthropic_structured_output_uses_a_forced_tool(config: Config, fake: FakeProvider) -> None:
    fake.reply(200, fixture("anthropic_structured.json"))
    schema = {"type": "object", "properties": {"answer": {"type": "string"}, "score": {"type": "integer"}}}
    resp, _ = run(
        config,
        request(response_format={"type": "json_schema", "name": "verdict", "schema": schema}),
        route("anthropic", "claude-haiku-4-5-20251001", base_url=fake.url),
    )
    assert resp["output"]["json"] == {"answer": "yes", "score": 3} and resp["output"]["tool_calls"] == []
    assert resp["finish_reason"] == "stop"
    assert fake.requests[0]["body"]["tool_choice"] == {"type": "tool", "name": "blux_structured_output"}


def test_anthropic_streaming_with_a_tool_call(config: Config, fake: FakeProvider) -> None:
    fake.reply(200, fixture("anthropic_stream.sse"))
    tools = [{"name": "lookup", "description": "l", "input_schema": {"type": "object"}}]
    resp, events = run(
        config, request(stream=True, tools=tools), route("anthropic", "claude-haiku-4-5-20251001", base_url=fake.url)
    )
    assert "".join(d["text"] for k, d in events if k == "delta") == "Hi there"
    assert resp["output"]["tool_calls"] == [{"id": "toolu_9", "name": "lookup", "arguments": {"q": "blux"}}]
    assert resp["usage"]["input_tokens"] == 9 and resp["usage"]["output_tokens"] == 15
    assert ("tool_call", resp["output"]["tool_calls"][0]) in events


def test_anthropic_tool_round_trip_message_shape(config: Config, fake: FakeProvider) -> None:
    fake.reply(200, fixture("anthropic_message.json"))
    req = request(
        messages=[
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "t1", "name": "lookup", "arguments": {"q": 1}}]},
            {"role": "tool", "tool_call_id": "t1", "content": "result"},
        ]
    )
    run(config, req, route("anthropic", "claude-haiku-4-5-20251001", base_url=fake.url))
    msgs = fake.requests[0]["body"]["messages"]
    assert msgs[1]["content"][0] == {"type": "tool_use", "id": "t1", "name": "lookup", "input": {"q": 1}}
    assert msgs[2] == {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "result"}]}


# Transport: retries, error mapping, timeouts, secrets ------------------------------------------------------


def test_rate_limit_is_retried_then_succeeds(config: Config, fake: FakeProvider) -> None:
    fake.reply(429, {"error": {"message": "slow down"}}, **{"retry-after": "0"}).reply(200, fixture("openai_chat.json"))
    resp, _ = run(config, request(), route("openai", "gpt-5-mini", base_url=fake.url))
    assert resp["routing"]["attempts"][0]["retries"] == 1 and len(fake.requests) == 2


def test_server_errors_exhaust_retries(config: Config, fake: FakeProvider) -> None:
    for _ in range(3):
        fake.reply(500, {"error": {"message": "boom"}})
    err = fail(config, request(), route("openai", "gpt-5-mini", base_url=fake.url))
    assert (err.code, err.retryable, err.fallback, err.details["retries"]) == ("PROVIDER_ERROR", True, True, 2)


@pytest.mark.parametrize(
    ("status", "message", "code", "calls"),
    [
        (401, "bad key", "PROVIDER_AUTH_FAILED", 1),
        (402, "Insufficient Balance", "PROVIDER_QUOTA_EXCEEDED", 1),
        (400, "Your credit balance is too low to access the API", "PROVIDER_QUOTA_EXCEEDED", 1),
        (400, "This model's maximum context length is 8192 tokens", "CONTEXT_TOO_LONG", 1),
        (400, "Output blocked by content filtering policy", "CONTENT_FILTERED", 1),
        (404, "model not found", "PROVIDER_REJECTED", 1),
        (503, "overloaded", "PROVIDER_UNAVAILABLE", 3),
    ],
)
def test_http_errors_are_normalized(
    config: Config, fake: FakeProvider, status: int, message: str, code: str, calls: int
) -> None:
    for _ in range(calls):
        fake.reply(status, {"error": {"message": message}})
    err = fail(config, request(), route("openai", "gpt-5-mini", base_url=fake.url))
    assert err.code == code and len(fake.requests) == calls


def test_unreachable_provider(config: Config) -> None:
    err = fail(config, request(), route("openai", "gpt-5-mini", base_url="http://127.0.0.1:9/v1"), retries=0)
    assert err.code == "PROVIDER_UNAVAILABLE"


def test_deadline_is_enforced(config: Config, fake: FakeProvider) -> None:
    fake.script.append((-1, {"sleep": "3"}, b""))
    t0 = time.monotonic()
    err = fail(config, request(), route("openai", "gpt-5-mini", base_url=fake.url), timeout=0.5, retries=0)
    assert err.code == "PROVIDER_TIMEOUT" and time.monotonic() - t0 < 2.5


def test_credentials_never_leak_into_errors(config: Config, fake: FakeProvider) -> None:
    fake.reply(401, {"error": {"message": f"Incorrect API key provided: {FAKE_KEY}"}})
    fake.reply(400, {"error": {"message": f"bad request with key {FAKE_KEY}"}})
    for _ in range(2):
        err = fail(config, request(), route("openai", "gpt-5-mini", base_url=fake.url))
        assert FAKE_KEY not in json.dumps(err.to_document())


def test_missing_key_is_not_configured(config: Config, fake: FakeProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "file", {})
    err = fail(config, request(), route("openai", "gpt-5-mini", base_url=fake.url))
    assert (err.code, err.fallback, fake.requests) == ("PROVIDER_NOT_CONFIGURED", True, [])


def test_local_openai_compatible_server_needs_no_key(
    config: Config, fake: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "file", {})
    fake.reply(200, fixture("openai_chat.json"))
    rt = {**route("openai-compatible", "local-gguf", base_url=fake.url), "locality": "local"}
    resp, _ = run(config, request(), rt)
    assert resp["provider"]["locality"] == "local" and "authorization" not in fake.requests[0]["headers"]
