"""Anthropic Messages API.

Structured output uses a forced tool whose input schema is the requested JSON Schema; its input becomes
`output.json`. Thinking blocks are dropped: BLUX records explicit outputs, never hidden reasoning.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

from bluxgpt.api import ModelError, response, system_text, usage
from bluxgpt.transport import Transport

API_VERSION = "2023-06-01"
STRUCTURED_TOOL = "blux_structured_output"
FINISH = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "refusal": "content_filter",
    "pause_turn": "other",
}


class Anthropic:
    name = "anthropic"

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
        key = config.secret("ANTHROPIC_API_KEY")
        if not key:
            raise ModelError(
                "PROVIDER_NOT_CONFIGURED",
                "ANTHROPIC_API_KEY is not set.",
                provider=route["provider"],
                route_id=route["route_id"],
            )
        base = (route.get("base_url") or "https://api.anthropic.com/v1").rstrip("/")
        headers = {"x-api-key": key, "anthropic-version": API_VERSION}
        started = time.monotonic()
        structured = (request.get("response_format") or {}).get("type") == "json_schema"
        stream = bool(request.get("stream")) and not structured
        result = transport.post(
            base + "/messages",
            headers,
            self.body(request, route, stream=stream),
            deadline=deadline,
            cancel=cancel,
            provider=route["provider"],
            route_id=route["route_id"],
            secrets=(key,),
            stream=stream,
        )
        if stream:
            assert not isinstance(result, dict)
            text, calls, finish, use, req_id, first = self._read_stream(result, route, cancel, emit, started)
        else:
            assert isinstance(result, dict)
            text, calls, finish, use, req_id, first = self._read_body(result)
            if request.get("stream"):  # structured output is not streamed; still honour the event contract
                if text:
                    emit("delta", {"text": text})
                emit("usage", use)
        json_value = None
        if structured:
            forced = [c for c in calls if c["name"] == STRUCTURED_TOOL]
            if not forced:
                raise ModelError(
                    "STRUCTURED_OUTPUT_INVALID",
                    "The model did not return the structured output.",
                    provider=route["provider"],
                    route_id=route["route_id"],
                )
            json_value = forced[0]["arguments"]
            calls = [c for c in calls if c["name"] != STRUCTURED_TOOL]
            finish = "stop" if finish == "tool_calls" and not calls else finish
        return response(
            request,
            route,
            text=text,
            json_value=json_value,
            tool_calls=calls,
            finish_reason=finish,
            usage_doc=use,
            request_id=req_id,
            latency_ms=int((time.monotonic() - started) * 1000),
            first_token_ms=first,
            retries=transport.retries,
        )

    def body(self, request: dict[str, Any], route: dict[str, Any], *, stream: bool) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        for msg in request["messages"]:
            if msg["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": msg["tool_call_id"], "content": msg["content"]}
                if (
                    messages
                    and messages[-1]["role"] == "user"
                    and isinstance(messages[-1]["content"], list)
                    and all(b.get("type") == "tool_result" for b in messages[-1]["content"])
                ):
                    messages[-1]["content"].append(block)
                else:
                    messages.append({"role": "user", "content": [block]})
            elif msg.get("tool_calls"):
                blocks: list[dict[str, Any]] = [{"type": "text", "text": msg["content"]}] if msg["content"] else []
                blocks += [
                    {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]}
                    for c in msg["tool_calls"]
                ]
                messages.append({"role": "assistant", "content": blocks})
            else:
                messages.append({"role": msg["role"], "content": msg["content"]})
        gen = request.get("generation") or {}
        body: dict[str, Any] = {
            "model": route["provider_model"],
            "messages": messages,
            "max_tokens": gen.get("max_output_tokens", 4096),
        }
        system = system_text(request)
        if system:
            body["system"] = system
        for key in ("temperature", "top_p"):
            if key in gen:
                body[key] = gen[key]
        if gen.get("stop"):
            body["stop_sequences"] = gen["stop"]
        tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
            for t in request.get("tools") or []
        ]
        fmt = request.get("response_format") or {}
        choice = request.get("tool_choice", "auto")
        if fmt.get("type") == "json_schema":
            tools.append(
                {
                    "name": STRUCTURED_TOOL,
                    "description": f"Return the {fmt['name']} result.",
                    "input_schema": fmt["schema"],
                }
            )
            body["tool_choice"] = {"type": "tool", "name": STRUCTURED_TOOL}
        elif tools:
            body["tool_choice"] = (
                {"type": "auto"}
                if choice == "auto"
                else {"type": "any"}
                if choice == "required"
                else {"type": "none"}
                if choice == "none"
                else {"type": "tool", "name": choice["name"]}
            )
        if tools:
            body["tools"] = tools
        if stream:
            body["stream"] = True
        return body

    def _read_body(self, doc: dict[str, Any]) -> tuple[Any, ...]:
        text, calls = [], []
        for block in doc.get("content") or []:
            if block.get("type") == "text":
                text.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                calls.append(
                    {"id": str(block.get("id"))[:128], "name": block.get("name"), "arguments": block.get("input") or {}}
                )
        u = doc.get("usage") or {}
        return (
            "".join(text) or None,
            calls,
            FINISH.get(doc.get("stop_reason") or "end_turn", "other"),
            usage(u.get("input_tokens"), u.get("output_tokens"), cached=u.get("cache_read_input_tokens")),
            doc.get("id"),
            None,
        )

    def _read_stream(
        self,
        events: Iterator[bytes],
        route: dict[str, Any],
        cancel: threading.Event,
        emit: Callable[[str, dict[str, Any]], None],
        started: float,
    ) -> tuple[Any, ...]:
        text: list[str] = []
        blocks: dict[int, dict[str, Any]] = {}
        finish, req_id, first = "stop", None, None
        in_tokens = out_tokens = cached = None
        for data in events:
            if cancel.is_set():
                raise ModelError(
                    "CANCELLED", "Cancelled by the caller.", provider=route["provider"], route_id=route["route_id"]
                )
            try:
                ev = json.loads(data)
            except ValueError:
                raise ModelError(
                    "PROVIDER_ERROR",
                    "The provider sent a malformed stream event.",
                    provider=route["provider"],
                    route_id=route["route_id"],
                ) from None
            kind = ev.get("type")
            if kind == "error":
                err = ev.get("error") or {}
                code = {
                    "overloaded_error": "PROVIDER_UNAVAILABLE",
                    "rate_limit_error": "PROVIDER_RATE_LIMITED",
                    "api_error": "PROVIDER_ERROR",
                }.get(str(err.get("type")), "PROVIDER_ERROR")
                raise ModelError(
                    code,
                    str(err.get("message", "stream error")),
                    provider=route["provider"],
                    route_id=route["route_id"],
                )
            if kind == "message_start":
                msg = ev.get("message") or {}
                req_id = msg.get("id")
                u = msg.get("usage") or {}
                in_tokens, cached = u.get("input_tokens"), u.get("cache_read_input_tokens")
            elif kind == "content_block_start":
                block = ev.get("content_block") or {}
                if block.get("type") == "tool_use":
                    blocks[ev.get("index", 0)] = {"id": block.get("id"), "name": block.get("name"), "json": ""}
            elif kind == "content_block_delta":
                delta = ev.get("delta") or {}
                if delta.get("type") == "text_delta":
                    if first is None:
                        first = int((time.monotonic() - started) * 1000)
                    text.append(delta.get("text", ""))
                    emit("delta", {"text": delta.get("text", "")})
                elif delta.get("type") == "input_json_delta" and ev.get("index", 0) in blocks:
                    blocks[ev.get("index", 0)]["json"] += delta.get("partial_json", "")
            elif kind == "message_delta":
                finish = FINISH.get((ev.get("delta") or {}).get("stop_reason") or "end_turn", "other")
                out_tokens = (ev.get("usage") or {}).get("output_tokens", out_tokens)
        calls = []
        for _, b in sorted(blocks.items()):
            try:
                args = json.loads(b["json"] or "{}")
            except ValueError:
                raise ModelError(
                    "TOOL_CALL_INVALID",
                    f"Tool call {b['name']!r} has arguments that are not JSON.",
                    provider=route["provider"],
                    route_id=route["route_id"],
                ) from None
            call = {"id": str(b["id"])[:128], "name": b["name"], "arguments": args}
            calls.append(call)
            emit("tool_call", call)
        use = usage(in_tokens, out_tokens, cached=cached)
        emit("usage", use)
        return "".join(text) or None, calls, finish, use, req_id, first
