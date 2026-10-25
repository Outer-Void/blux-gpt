"""`bluxgpt blux-model-backend`: the BLUX model-backend protocol (BLUX ADR-0010).

stdin   {"model_api_version": "1.0", "request": <blux.model-request>, "route": <route>, "context": {..., "deadline_ms"}}
stdout  blux.model-stream-event lines; the last is "end" (with the response) or "error"; exit 0

BluxGPT owns transport, retries, streaming, timeouts and normalization here. Routing, fallback, policy and
receipts belong to BLUX. Nothing in this process runs tools or acts on output.
"""

from __future__ import annotations

import json
import signal
import sys
import threading
import time
from typing import IO, Any

from bluxgpt.api import MODEL_API_VERSION, ModelError, event
from bluxgpt.gateway import Gateway


def main(stdin: IO[str] | None = None, stdout: IO[str] | None = None, gateway: Gateway | None = None) -> int:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    cancel = threading.Event()
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, lambda *_: cancel.set())
    seq = 0

    def emit(kind: str, data: dict[str, Any]) -> None:
        nonlocal seq
        stdout.write(json.dumps(event(seq, kind, data), separators=(",", ":")) + "\n")
        stdout.flush()
        seq += 1

    route: dict[str, Any] = {}
    try:
        payload = json.loads(stdin.read())
        if not isinstance(payload, dict) or payload.get("model_api_version") != MODEL_API_VERSION:
            raise ModelError("BACKEND_PROTOCOL_ERROR", "Expected a model-backend payload for model_api_version 1.0.")
        request, route, context = payload["request"], payload["route"], payload.get("context") or {}
        deadline = time.monotonic() + int(context.get("deadline_ms", 120000)) / 1000
        gw = gateway or Gateway()
        response = gw.generate(request, route, deadline=deadline, cancel=cancel, emit=emit)
        emit("end", {"response": response})
    except ModelError as exc:
        exc.provider = exc.provider or route.get("provider")
        exc.route_id = exc.route_id or route.get("route_id")
        emit("error", {"error": exc.to_document()})
    except (ValueError, KeyError, TypeError) as exc:
        emit(
            "error",
            {
                "error": ModelError(
                    "BACKEND_PROTOCOL_ERROR",
                    f"Bad backend payload ({type(exc).__name__}).",
                    provider=route.get("provider"),
                    route_id=route.get("route_id"),
                ).to_document()
            },
        )
    except Exception as exc:  # noqa: BLE001 - the protocol must always end with an event
        emit(
            "error",
            {
                "error": ModelError(
                    "INTERNAL_ERROR",
                    f"Internal BluxGPT error ({type(exc).__name__}).",
                    provider=route.get("provider"),
                    route_id=route.get("route_id"),
                ).to_document()
            },
        )
    return 0
