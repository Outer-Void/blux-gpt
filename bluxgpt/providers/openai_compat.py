"""OpenAI Chat Completions, and APIs compatible with it (DeepSeek, llama.cpp's llama-server, others).

Reasoning text some providers return (DeepSeek's `reasoning_content`) is dropped: only its token count is
kept. BLUX records explicit outputs, never a model's hidden reasoning.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

from bluxgpt.api import ModelError, response, system_text, usage
from bluxgpt.transport import Transport

FINISH = {
    "stop": "stop",
    "length": "length",
    "tool_calls": "tool_calls",
    "function_call": "tool_calls",
    "content_filter": "content_filter",
}


class OpenAICompatible:
    def __init__(self, name: str, *, base_url: str | None, key_name: str | None, flavor: str) -> None:
        self.name = name
        self.default_base = base_url
        self.key_name = key_name
        self.flavor = flavor  # "openai" | "deepseek" | "generic"

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
        base = route.get("base_url") or self.default_base
        if not base:
            raise ModelError(
                "PROVIDER_NOT_CONFIGURED",
                f"{self.name} needs a base_url on the route.",
                provider=route["provider"],
                route_id=route["route_id"],
            )
        key = config.secret(self.key_name) if self.key_name else None
        if self.key_name and not key and self.flavor != "generic":
            raise ModelError(
                "PROVIDER_NOT_CONFIGURED",
                f"{self.key_name} is not set.",
                provider=route["provider"],
                route_id=route["route_id"],
            )
        headers = {"authorization": f"Bearer {key}"} if key else {}
        body = self.body(request, route)
        started = time.monotonic()
        secrets = tuple(v for v in (key,) if v)
        stream = bool(request.get("stream"))
        result = transport.post(
            base.rstrip("/") + "/chat/completions",
            headers,
            body,
            deadline=deadline,
            cancel=cancel,
            provider=route["provider"],
            route_id=route["route_id"],
            secrets=secrets,
            stream=stream,
        )
        if stream:
            assert not isinstance(result, dict)
            text, calls, finish, use, req_id, first = self._read_stream(result, route, cancel, emit, started)
        else:
            assert isinstance(result, dict)
            text, calls, finish, use, req_id, first = self._read_body(result, route)
        return _finish(request, route, text, calls, finish, use, req_id, started, first, transport.retries)

    def body(self, request: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        system = system_text(request)
        fmt = request.get("response_format") or {}
        if fmt.get("type") == "json_schema" and self.flavor != "openai":
            note = (
                "Reply with only a JSON object (no prose, no code fence) that matches this JSON Schema:\n"
                + json.dumps(fmt["schema"], sort_keys=True)
            )
            system = f"{system}\n\n{note}" if system else note
        if system:
            messages.append({"role": "system", "content": system})
        for msg in request["messages"]:
            if msg["role"] == "tool":
                messages.append({"role": "tool", "tool_call_id": msg["tool_call_id"], "content": msg["content"]})
            elif msg.get("tool_calls"):
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg["content"] or None,
                        "tool_calls": [
                            {
                                "id": c["id"],
                                "type": "function",
                                "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])},
                            }
                            for c in msg["tool_calls"]
                        ],
                    }
                )
            else:
                messages.append({"role": msg["role"], "content": msg["content"]})
        body: dict[str, Any] = {"model": route["provider_model"], "messages": messages}
        if request.get("tools") and request.get("tool_choice") != "none":
            body["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]},
                }
                for t in request["tools"]
            ]
            choice = request.get("tool_choice", "auto")
            body["tool_choice"] = (
                choice if isinstance(choice, str) else {"type": "function", "function": {"name": choice["name"]}}
            )
        if fmt.get("type") == "json_schema":
            body["response_format"] = (
                {
                    "type": "json_schema",
                    "json_schema": {
                        "name": fmt["name"],
                        "schema": fmt["schema"],
                        "strict": bool(fmt.get("strict", False)),
                    },
                }
                if self.flavor == "openai"
                else {"type": "json_object"}
            )
        gen = request.get("generation") or {}
        if "max_output_tokens" in gen:
            body["max_completion_tokens" if self.flavor == "openai" else "max_tokens"] = gen["max_output_tokens"]
        for key in ("temperature", "top_p", "seed"):
            if key in gen:
                body[key] = gen[key]
        if gen.get("stop"):
            body["stop"] = gen["stop"]
        if request.get("stream"):
            body["stream"] = True
            body["stream_options"] = {"include_usage": True}
        return body

    def _read_body(self, doc: dict[str, Any], route: dict[str, Any]) -> tuple[Any, ...]:
        try:
            choice = doc["choices"][0]
            msg = choice["message"]
        except (KeyError, IndexError, TypeError):
            raise ModelError(
                "PROVIDER_ERROR",
                "The provider returned no choices.",
                provider=route["provider"],
                route_id=route["route_id"],
            ) from None
        calls = [
            _call(c.get("id"), (c.get("function") or {}).get("name"), (c.get("function") or {}).get("arguments"), route)
            for c in msg.get("tool_calls") or []
        ]
        return (
            msg.get("content"),
            calls,
            FINISH.get(choice.get("finish_reason") or "stop", "other"),
            _usage(doc.get("usage")),
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
        calls: dict[int, dict[str, Any]] = {}
        finish = "stop"
        use = usage()
        req_id = None
        first = None
        for data in events:
            if cancel.is_set():
                raise ModelError(
                    "CANCELLED", "Cancelled by the caller.", provider=route["provider"], route_id=route["route_id"]
                )
            if data.strip() == b"[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                raise ModelError(
                    "PROVIDER_ERROR",
                    "The provider sent a malformed stream chunk.",
                    provider=route["provider"],
                    route_id=route["route_id"],
                ) from None
            req_id = req_id or chunk.get("id")
            if chunk.get("usage"):
                use = _usage(chunk["usage"])
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    if first is None:
                        first = int((time.monotonic() - started) * 1000)
                    text.append(delta["content"])
                    emit("delta", {"text": delta["content"]})
                for tc in delta.get("tool_calls") or []:
                    slot = calls.setdefault(tc.get("index", 0), {"id": None, "name": "", "arguments": ""})
                    slot["id"] = tc.get("id") or slot["id"]
                    fn = tc.get("function") or {}
                    slot["name"] += fn.get("name") or ""
                    slot["arguments"] += fn.get("arguments") or ""
                if choice.get("finish_reason"):
                    finish = FINISH.get(choice["finish_reason"], "other")
        parsed = [_call(c["id"], c["name"], c["arguments"], route) for _, c in sorted(calls.items())]
        for call in parsed:
            emit("tool_call", call)
        emit("usage", use)
        return "".join(text) if text else None, parsed, finish, use, req_id, first


def _call(call_id: Any, name: Any, arguments: Any, route: dict[str, Any]) -> dict[str, Any]:
    try:
        args = json.loads(arguments or "{}") if isinstance(arguments, str) else (arguments or {})
    except ValueError:
        raise ModelError(
            "TOOL_CALL_INVALID",
            f"Tool call {name!r} has arguments that are not JSON.",
            provider=route["provider"],
            route_id=route["route_id"],
        ) from None
    if not isinstance(args, dict) or not name:
        raise ModelError(
            "TOOL_CALL_INVALID",
            "A tool call has no name or non-object arguments.",
            provider=route["provider"],
            route_id=route["route_id"],
        )
    return {"id": str(call_id or f"call_{name}")[:128], "name": str(name), "arguments": args}


def _usage(doc: Any) -> dict[str, Any]:
    if not isinstance(doc, dict):
        return usage()
    details = doc.get("completion_tokens_details") or {}
    prompt = doc.get("prompt_tokens_details") or {}
    cached = prompt.get("cached_tokens", doc.get("prompt_cache_hit_tokens"))
    return usage(
        doc.get("prompt_tokens"),
        doc.get("completion_tokens"),
        reasoning=details.get("reasoning_tokens"),
        cached=cached,
        total=doc.get("total_tokens"),
    )


def _finish(
    request: dict[str, Any],
    route: dict[str, Any],
    text: str | None,
    calls: list[dict[str, Any]],
    finish: str,
    use: dict[str, Any],
    req_id: Any,
    started: float,
    first: int | None,
    retries: int,
) -> dict[str, Any]:
    json_value = None
    if (request.get("response_format") or {}).get("type") == "json_schema":
        json_value = parse_json_output(text, route)
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
        retries=retries,
    )


def parse_json_output(text: str | None, route: dict[str, Any]) -> Any:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("\n") + 1 :] if "\n" in raw else raw
    try:
        return json.loads(raw)
    except ValueError:
        raise ModelError(
            "STRUCTURED_OUTPUT_INVALID",
            "The model's output is not valid JSON.",
            provider=route["provider"],
            route_id=route["route_id"],
        ) from None
