"""Model API v1 primitives BluxGPT needs: logical models, normalized errors, ids and documents.

BluxGPT implements the BLUX Model API v1 (docs: Outer-Void/blux docs/model-api/v1.md) without importing
BLUX. Its output is checked against BLUX's published schemas in the integration tests.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

MODEL_API_VERSION = "1.0"
LOGICAL_MODELS = ("blux-main", "blux-fast", "blux-reason", "blux-code")

# code -> (retryable, fallback), identical to blux_sdk.model_api.ERRORS
ERRORS: dict[str, tuple[bool, bool]] = {
    "INVALID_REQUEST": (False, False), "UNKNOWN_MODEL": (False, False), "CAPABILITY_UNAVAILABLE": (False, False),
    "PROVIDER_NOT_CONFIGURED": (False, True), "PROVIDER_AUTH_FAILED": (False, True),
    "PROVIDER_RATE_LIMITED": (True, True), "PROVIDER_QUOTA_EXCEEDED": (False, True),
    "PROVIDER_UNAVAILABLE": (True, True), "PROVIDER_ERROR": (True, True),
    "PROVIDER_TIMEOUT": (True, True), "PROVIDER_REJECTED": (False, False), "CONTEXT_TOO_LONG": (False, True),
    "CONTENT_FILTERED": (False, False), "STRUCTURED_OUTPUT_INVALID": (True, True), "TOOL_CALL_INVALID": (True, True),
    "BACKEND_PROTOCOL_ERROR": (True, True), "ALL_ROUTES_FAILED": (True, False), "TIMEOUT": (True, False),
    "CANCELLED": (False, False), "INTERNAL_ERROR": (False, False),
}  # fmt: skip
# Codes a transport retries on the same route before giving up.
TRANSPORT_RETRY = frozenset({"PROVIDER_RATE_LIMITED", "PROVIDER_UNAVAILABLE", "PROVIDER_ERROR", "PROVIDER_TIMEOUT"})

_SECRET_RE = re.compile(
    "|".join(
        f"(?:{p})"
        for p in (
            r"sk-ant-[A-Za-z0-9_-]{16,}",
            r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}",
            r"gh[pousr]_[A-Za-z0-9]{30,}",
            r"(?:AKIA|ASIA)[0-9A-Z]{16}",
            r"AIza[0-9A-Za-z_-]{35}",
            r"xox[baprs]-[A-Za-z0-9-]{10,}",
            r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
            r"\b[Bb][Ee][Aa][Rr][Ee][Rr]\s+[A-Za-z0-9._~+/=-]{12,}",
            r"(?:[Aa][Pp][Ii][_-]?[Kk][Ee][Yy]|[Xx]-[Aa][Pp][Ii]-[Kk][Ee][Yy]|[Aa]uthorization)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{12,}",
            r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)",
        )
    )
)
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def scrub(text: str, secrets: tuple[str, ...] = ()) -> str:
    """Remove credential-shaped strings, and the given secret values, from text."""
    for value in secrets:
        if value and len(value) >= 8:
            text = text.replace(value, "[redacted]")
    return _SECRET_RE.sub("[redacted]", text)


def scrub_doc(doc: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(doc, str):
        return scrub(doc, secrets)
    if isinstance(doc, list):
        return [scrub_doc(v, secrets) for v in doc]
    if isinstance(doc, dict):
        return {k: scrub_doc(v, secrets) for k, v in doc.items()}
    return doc


class ModelError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        provider: str | None = None,
        route_id: str | None = None,
        attempts: list[dict[str, Any]] | None = None,
        details: dict[str, Any] | None = None,
        retry_after: float | None = None,
    ) -> None:
        if code not in ERRORS:
            code, message = "INTERNAL_ERROR", f"{code}: {message}"
        super().__init__(message)
        self.code, self.message = code, scrub(message)[:512]
        self.provider, self.route_id = provider, route_id
        self.attempts = list(attempts or [])
        self.details = scrub_doc(dict(details or {}))
        self.retry_after = retry_after

    @property
    def retryable(self) -> bool:
        return ERRORS[self.code][0]

    @property
    def fallback(self) -> bool:
        return ERRORS[self.code][1]

    def to_document(self) -> dict[str, Any]:
        return {
            "contract": "blux.model-error",
            "model_api_version": MODEL_API_VERSION,
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "fallback": self.fallback,
            "provider": self.provider,
            "route_id": self.route_id,
            "attempts": self.attempts,
            "details": self.details,
        }


def ulid() -> str:
    value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    return "".join(_CROCKFORD[(value >> (5 * i)) & 31] for i in reversed(range(26)))


def event(seq: int, kind: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": "blux.model-stream-event",
        "model_api_version": MODEL_API_VERSION,
        "seq": seq,
        "type": kind,
        "data": data,
    }


def usage(
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    *,
    reasoning: int | None = None,
    cached: int | None = None,
    total: int | None = None,
) -> dict[str, Any]:
    reported = any(v is not None for v in (input_tokens, output_tokens, total))
    if total is None and input_tokens is not None and output_tokens is not None:
        total = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "reasoning_tokens": reasoning,
        "cached_input_tokens": cached,
        "reported_by_provider": reported,
    }


def response(
    request: dict[str, Any],
    route: dict[str, Any],
    *,
    text: str | None,
    json_value: Any = None,
    tool_calls: list[dict[str, Any]] | None = None,
    finish_reason: str,
    usage_doc: dict[str, Any],
    request_id: str | None,
    latency_ms: int,
    first_token_ms: int | None,
    retries: int,
    backend: str = "bluxgpt",
) -> dict[str, Any]:
    tool_calls = tool_calls or []
    status = (
        "tool_calls" if tool_calls else "incomplete" if finish_reason in ("length", "content_filter") else "completed"
    )
    return {
        "contract": "blux.model-response",
        "model_api_version": MODEL_API_VERSION,
        "response_id": "mresp_" + ulid(),
        "model": request["model"],
        "status": status,
        "finish_reason": finish_reason,
        "output": {"text": text, "json": json_value, "tool_calls": tool_calls},
        "usage": usage_doc,
        "provider": {
            "backend": backend,
            "provider": route["provider"],
            "provider_model": route["provider_model"],
            "route_id": route["route_id"],
            "locality": route["locality"],
            "request_id": (request_id or None) and str(request_id)[:128],
        },
        "routing": {
            "route_id": route["route_id"],
            "fallback_used": False,
            "degraded": False,
            "notes": [],
            "attempts": [
                {
                    "route_id": route["route_id"],
                    "provider": route["provider"],
                    "provider_model": route["provider_model"],
                    "outcome": "succeeded",
                    "error_code": None,
                    "retryable": None,
                    "reason": None,
                    "latency_ms": latency_ms,
                    "retries": retries,
                }
            ],
        },
        "determinism": {
            "requested": bool(request.get("deterministic")),
            "supported": False,
            "applied": {
                "temperature": (request.get("generation") or {}).get("temperature"),
                "seed": (request.get("generation") or {}).get("seed"),
            },
        },
        "timing": {"latency_ms": latency_ms, "first_token_ms": first_token_ms},
        "linkage": None,
    }


def system_text(request: dict[str, Any]) -> str | None:
    """System instructions plus context items, as one system string (providers have one system slot)."""
    parts = [request["system"]] if request.get("system") else []
    for item in request.get("context") or []:
        title = f" {item['title']}" if item.get("title") else ""
        parts.append(f"[context: {item['kind']}{title}]\n{item['content']}")
    return "\n\n".join(parts) or None
