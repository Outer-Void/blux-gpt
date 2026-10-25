"""HTTP transport: one place for timeouts, retries, error mapping and Server-Sent Events.

Standard library only (urllib). Every call has a deadline. Retryable failures (rate limit, 5xx, network
errors, timeouts) are retried on the same route with exponential backoff, honoring Retry-After, while time
remains; then the normalized error goes back to the router, which decides on fallback. Credentials appear
only in request headers, and every provider message is scrubbed of them before it is raised.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

from bluxgpt.api import TRANSPORT_RETRY, ModelError

USER_AGENT = "bluxgpt/2.0 (+https://github.com/Outer-Void/blux-gpt)"


class Transport:
    def __init__(
        self,
        *,
        max_retries: int = 2,
        backoff_s: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self.sleep = sleep
        self.opener = opener
        self.retries = 0

    def post(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        *,
        deadline: float,
        cancel: threading.Event,
        provider: str,
        route_id: str,
        secrets: tuple[str, ...],
        stream: bool = False,
    ) -> Iterator[bytes] | dict[str, Any]:
        """POST JSON. Returns the decoded JSON body, or (stream=True) an iterator of SSE data payloads."""
        attempt = 0
        while True:
            if cancel.is_set():
                raise ModelError("CANCELLED", "Cancelled by the caller.", provider=provider, route_id=route_id)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ModelError(
                    "PROVIDER_TIMEOUT",
                    "The provider did not answer before the deadline.",
                    provider=provider,
                    route_id=route_id,
                    details={"retries": self.retries},
                )
            try:
                return self._once(
                    url,
                    headers,
                    body,
                    timeout=remaining,
                    provider=provider,
                    route_id=route_id,
                    secrets=secrets,
                    stream=stream,
                )
            except ModelError as exc:
                exc.details["retries"] = self.retries
                if exc.code not in TRANSPORT_RETRY or attempt >= self.max_retries:
                    raise
                wait = exc.retry_after if exc.retry_after is not None else self.backoff_s * (2**attempt)
                if time.monotonic() + wait >= deadline:
                    raise
                attempt += 1
                self.retries += 1
                self._wait(wait, cancel)

    def _wait(self, seconds: float, cancel: threading.Event) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if cancel.is_set():
                return
            self.sleep(min(0.05, max(0.0, end - time.monotonic())))

    def _once(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        *,
        timeout: float,
        provider: str,
        route_id: str,
        secrets: tuple[str, ...],
        stream: bool,
    ) -> Iterator[bytes] | dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream" if stream else "application/json",
                "user-agent": USER_AGENT,
                **headers,
            },
        )

        def fail(code: str, message: str, **extra: Any) -> ModelError:
            return ModelError(code, message, provider=provider, route_id=route_id, **extra)

        try:
            resp = self.opener(req, timeout=max(0.1, timeout))
        except urllib.error.HTTPError as exc:
            raw = exc.read()[:4096].decode("utf-8", "replace")
            raise _http_error(
                exc.code, raw, exc.headers.get("retry-after") if exc.headers else None, fail, secrets
            ) from None
        except TimeoutError:
            raise fail("PROVIDER_TIMEOUT", "The provider connection timed out.") from None
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise fail("PROVIDER_TIMEOUT", "The provider connection timed out.") from None
            raise fail("PROVIDER_UNAVAILABLE", f"Cannot reach the provider: {type(reason).__name__}.") from None
        except OSError as exc:
            raise fail("PROVIDER_UNAVAILABLE", f"Cannot reach the provider: {type(exc).__name__}.") from None
        if stream:
            return _sse(resp, fail)
        try:
            doc = json.loads(resp.read())
        except (ValueError, OSError):
            raise fail("PROVIDER_ERROR", "The provider returned a body that is not JSON.") from None
        finally:
            resp.close()
        if not isinstance(doc, dict):
            raise fail("PROVIDER_ERROR", "The provider returned an unexpected body.")
        return doc


def _http_error(
    status: int, raw: str, retry_after: str | None, fail: Callable[..., ModelError], secrets: tuple[str, ...]
) -> ModelError:
    from bluxgpt.api import scrub

    try:
        detail = json.loads(raw)
        message = (
            (detail.get("error") or {}).get("message")
            if isinstance(detail.get("error"), dict)
            else detail.get("message")
        )
    except ValueError:
        message = None
    message = scrub(str(message or raw or f"HTTP {status}"), secrets)[:300]
    lowered = message.lower()
    after = None
    if retry_after:
        try:
            after = min(30.0, max(0.0, float(retry_after)))
        except ValueError:
            after = None
    if status in (401, 403):
        return fail(
            "PROVIDER_AUTH_FAILED",
            f"The provider rejected the credentials (HTTP {status}).",
            details={"status": status},
        )
    if status == 402 or any(
        w in lowered
        for w in (
            "credit balance",
            "insufficient balance",
            "insufficient_quota",
            "exceeded your current quota",
            "billing",
        )
    ):
        return fail(
            "PROVIDER_QUOTA_EXCEEDED",
            f"The provider account has no usable balance or quota: {message}",
            details={"status": status},
        )
    if status == 429:
        return fail("PROVIDER_RATE_LIMITED", f"Rate limited: {message}", details={"status": status}, retry_after=after)
    if status in (408, 504):
        return fail("PROVIDER_TIMEOUT", f"The provider timed out (HTTP {status}).", details={"status": status})
    if status in (502, 503, 529):
        return fail(
            "PROVIDER_UNAVAILABLE",
            f"The provider is unavailable (HTTP {status}).",
            details={"status": status},
            retry_after=after,
        )
    if status >= 500:
        return fail("PROVIDER_ERROR", f"Provider error (HTTP {status}): {message}", details={"status": status})
    if "context" in lowered and ("length" in lowered or "too long" in lowered or "maximum" in lowered):
        return fail("CONTEXT_TOO_LONG", message, details={"status": status})
    if "content" in lowered and ("filter" in lowered or "policy" in lowered or "safety" in lowered):
        return fail("CONTENT_FILTERED", message, details={"status": status})
    return fail(
        "PROVIDER_REJECTED", f"The provider rejected the request (HTTP {status}): {message}", details={"status": status}
    )


def _sse(resp: Any, fail: Callable[..., ModelError]) -> Iterator[bytes]:
    """Yield the data payload of each Server-Sent Event."""
    try:
        data: list[bytes] = []
        for raw in resp:
            line = raw.rstrip(b"\r\n")
            if not line:
                if data:
                    yield b"\n".join(data)
                    data = []
                continue
            if line.startswith(b"data:"):
                data.append(line[5:].lstrip())
        if data:
            yield b"\n".join(data)
    except TimeoutError:
        raise fail("PROVIDER_TIMEOUT", "The provider stream stalled.") from None
    except OSError as exc:
        raise fail("PROVIDER_UNAVAILABLE", f"The provider stream broke: {type(exc).__name__}.") from None
    finally:
        resp.close()
