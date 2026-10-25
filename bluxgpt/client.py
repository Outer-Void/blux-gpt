"""Standalone client: BluxGPT without BLUX (ADR-0002), still targeting logical models.

Routes come from $BLUXGPT_ROUTES or the packaged default (the same blux.model-routes format BLUX uses).
Routes are tried in order; a route lacking a capability the request needs is skipped; a failure falls
back to the next route only when its error allows fallback. The response records every attempt, so a
fallback is never silent. Within BLUX, BLUX's router does this instead and BluxGPT is only the backend.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from typing import Any

from bluxgpt.api import LOGICAL_MODELS, MODEL_API_VERSION, ModelError
from bluxgpt.config import Config
from bluxgpt.gateway import Gateway


def load_routes(config: Config) -> dict[str, Any]:
    path = config.get("BLUXGPT_ROUTES")
    if path:
        doc: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    else:
        doc = json.loads(resources.files("bluxgpt").joinpath("data/routes.json").read_text(encoding="utf-8"))
    if doc.get("contract") != "blux.model-routes" or doc.get("model_api_version") != MODEL_API_VERSION:
        raise ModelError("INVALID_REQUEST", "The routes file is not a blux.model-routes 1.0 document.")
    return doc


def needed(request: dict[str, Any]) -> set[str]:
    caps = set(request.get("capabilities") or [])
    if request.get("stream"):
        caps.add("streaming")
    if request.get("tools") and request.get("tool_choice", "auto") != "none":
        caps.add("tools")
    if (request.get("response_format") or {}).get("type") == "json_schema":
        caps.add("structured_output")
    return caps


def generate(
    request: dict[str, Any],
    *,
    config: Config | None = None,
    gateway: Gateway | None = None,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    config = config or Config.load()
    gateway = gateway or Gateway(config)
    routes = load_routes(config)
    if request.get("model") not in LOGICAL_MODELS:
        raise ModelError("UNKNOWN_MODEL", f"Unknown logical model {request.get('model')!r}.")
    cancel = cancel or threading.Event()
    emit = on_event or (lambda kind, data: None)
    defaults = routes["defaults"]
    timeout_ms = min(request.get("timeout_ms", defaults["timeout_ms"]), defaults["timeout_ms"])
    t0 = time.monotonic()
    deadline = t0 + timeout_ms / 1000
    allow_fallback = (request.get("routing") or {}).get("allow_fallback", defaults["allow_fallback"])
    all_routes = routes["models"][request["model"]]["routes"]
    attempts: list[dict[str, Any]] = []
    last: ModelError | None = None
    tried = 0
    for route in all_routes:
        missing = sorted(needed(request) - set(route["capabilities"]) - {"local_only"})
        if missing or ("local_only" in needed(request) and route["locality"] != "local"):
            attempts.append(_attempt(route, "skipped", reason=f"route lacks {', '.join(missing) or 'local locality'}"))
            continue
        if (tried and (not allow_fallback or not (last and last.fallback))) or tried >= defaults["max_attempts"]:
            attempts.append(_attempt(route, "skipped", reason="no fallback"))
            continue
        tried += 1
        req = dict(request)
        gen = dict(req.get("generation") or {})
        if req.get("deterministic") and route["determinism"]["temperature"]:
            gen["temperature"] = 0
        if req.get("deterministic") and route["determinism"]["seed"]:
            gen.setdefault("seed", 0)
        if not route["determinism"]["temperature"]:
            gen.pop("temperature", None)
        if not route["determinism"]["seed"]:
            gen.pop("seed", None)
        req["generation"] = gen
        if not gen:
            req.pop("generation")
        started = time.monotonic()
        try:
            resp = gateway.generate(req, route, deadline=deadline, cancel=cancel, emit=emit)
        except ModelError as exc:
            attempts.append(_attempt(route, "failed", error=exc, latency_ms=int((time.monotonic() - started) * 1000)))
            last = exc
            if not exc.fallback or not allow_fallback:
                break
            continue
        attempts.append(
            _attempt(
                route,
                "succeeded",
                latency_ms=int((time.monotonic() - started) * 1000),
                retries=resp["routing"]["attempts"][-1]["retries"],
            )
        )
        primary = all_routes[0]["route_id"]
        resp["routing"] = {
            "route_id": route["route_id"],
            "attempts": attempts,
            "fallback_used": tried > 1,
            "degraded": route["route_id"] != primary or route["tier"] == "fallback",
            "notes": [f"served by {route['route_id']}"] if route["route_id"] != primary else [],
        }
        resp["determinism"] = {
            "requested": bool(request.get("deterministic")),
            "supported": route["determinism"]["temperature"] or route["determinism"]["seed"],
            "applied": {"temperature": gen.get("temperature"), "seed": gen.get("seed")},
        }
        resp["timing"]["latency_ms"] = int((time.monotonic() - t0) * 1000)
        return resp
    if last is not None and (not last.fallback or not allow_fallback):
        last.attempts = attempts
        raise last
    raise ModelError(
        "ALL_ROUTES_FAILED" if last else "CAPABILITY_UNAVAILABLE",
        f"No route for {request['model']} succeeded."
        if last
        else f"No route for {request['model']} provides what the request needs.",
        attempts=attempts,
    )


def _attempt(
    route: dict[str, Any],
    outcome: str,
    *,
    error: ModelError | None = None,
    reason: str | None = None,
    latency_ms: int | None = None,
    retries: int = 0,
) -> dict[str, Any]:
    return {
        "route_id": route["route_id"],
        "provider": route["provider"],
        "provider_model": route["provider_model"],
        "outcome": outcome,
        "error_code": error.code if error else None,
        "retryable": error.retryable if error else None,
        "reason": (reason or (error.message if error else None) or None),
        "latency_ms": latency_ms,
        "retries": int(error.details.get("retries", 0)) if error else retries,
    }
