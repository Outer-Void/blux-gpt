"""BluxGPT's documents conform to BLUX's published Model API v1 schemas (needs blux-sdk >= 0.2; CI installs it)."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest

from bluxgpt import backend
from bluxgpt.api import ERRORS
from tests.conftest import request, route

model_api = pytest.importorskip("blux_sdk.model_api")


def events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out = io.StringIO()
    backend.main(io.StringIO(json.dumps(payload)), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


@pytest.mark.parametrize("behaviour", ["echo", "json", "tool", "fail-provider_unavailable", "leak", "badjson"])
def test_backend_events_match_the_blux_schemas(config: Any, behaviour: str) -> None:
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}}
    req = request(
        stream=True,
        tools=[{"name": "t", "description": "", "input_schema": {"type": "object"}}],
        response_format={"type": "json_schema", "name": "n", "schema": schema},
    )
    for ev in events(
        {"model_api_version": "1.0", "request": req, "route": route("mock", behaviour, route_id="main.a")}
    ):
        assert model_api.schema_errors("stream-event", ev) == [], ev


def test_error_table_matches_blux() -> None:
    assert ERRORS == model_api.ERRORS


def test_packaged_routes_match_the_blux_routes_schema() -> None:
    from pathlib import Path

    from bluxgpt import cli

    for name in ("routes.json", "mock-routes.json"):
        doc = json.loads((Path(cli.__file__).parent / "data" / name).read_text())
        assert model_api.schema_errors("routes", doc) == [], name
