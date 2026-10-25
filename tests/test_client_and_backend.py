"""Logical-model routing, the BLUX backend protocol, the CLI and secret hygiene (MOCKED providers)."""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path
from typing import Any

import pytest

from bluxgpt import backend, cli, client
from bluxgpt.api import ModelError
from bluxgpt.config import Config, parse_env_file
from bluxgpt.providers.mock import FAKE_SECRET, minimal
from tests.conftest import FAKE_KEY, request, route


def routes_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    routes: list[dict[str, Any]],
    model: str = "blux-main",
    **defaults: Any,
) -> None:
    base = json.loads((Path(cli.__file__).parent / "data" / "mock-routes.json").read_text())
    base["models"][model]["routes"] = routes
    base["defaults"].update(defaults)
    path = tmp_path / "routes.json"
    path.write_text(json.dumps(base))
    monkeypatch.setenv("BLUXGPT_ROUTES", str(path))


def mock(model: str, route_id: str, **kw: Any) -> dict[str, Any]:
    return route("mock", model, route_id=route_id, **kw)


def test_a_logical_model_needs_no_provider_knowledge(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    routes_file(tmp_path, monkeypatch, [mock("echo", "main.a")])
    resp = client.generate(request(prompt="hi"), config=Config.load())
    assert resp["model"] == "blux-main" and resp["output"]["text"] == "echo: hi"
    assert resp["provider"]["provider"] == "mock" and resp["routing"]["degraded"] is False


def test_fallback_is_explicit(config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    routes_file(
        tmp_path, monkeypatch, [mock("fail-provider_unavailable", "main.a"), mock("echo", "main.b", tier="fallback")]
    )
    resp = client.generate(request(), config=Config.load())
    routing = resp["routing"]
    assert routing["route_id"] == "main.b" and routing["fallback_used"] and routing["degraded"]
    assert [(a["route_id"], a["outcome"], a["error_code"]) for a in routing["attempts"]] == [
        ("main.a", "failed", "PROVIDER_UNAVAILABLE"),
        ("main.b", "succeeded", None),
    ]


def test_safety_refusals_are_never_routed_around(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    routes_file(tmp_path, monkeypatch, [mock("fail-content_filtered", "main.a"), mock("echo", "main.b")])
    with pytest.raises(ModelError) as info:
        client.generate(request(), config=Config.load())
    assert info.value.code == "CONTENT_FILTERED" and len(info.value.attempts) == 1


def test_all_routes_failing_fails_explicitly(config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    routes_file(
        tmp_path, monkeypatch, [mock("fail-provider_quota_exceeded", "main.a"), mock("fail-provider_timeout", "main.b")]
    )
    with pytest.raises(ModelError) as info:
        client.generate(request(), config=Config.load())
    assert info.value.code == "ALL_ROUTES_FAILED"
    assert [a["error_code"] for a in info.value.attempts] == ["PROVIDER_QUOTA_EXCEEDED", "PROVIDER_TIMEOUT"]


def test_routes_without_a_needed_capability_are_skipped(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    routes_file(tmp_path, monkeypatch, [mock("echo", "main.a", caps=("streaming",)), mock("json", "main.b")])
    schema = {"type": "object", "required": ["n"], "properties": {"n": {"type": "integer", "minimum": 2}}}
    resp = client.generate(
        request(response_format={"type": "json_schema", "name": "n", "schema": schema}), config=Config.load()
    )
    assert resp["output"]["json"] == {"n": 2}
    assert resp["routing"]["attempts"][0]["outcome"] == "skipped"


def test_deterministic_controls_only_where_supported(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    routes_file(tmp_path, monkeypatch, [mock("echo", "main.a", temperature=True, seed=True)])
    resp = client.generate(request(deterministic=True, generation={"temperature": 0.9}), config=Config.load())
    assert resp["determinism"] == {"requested": True, "supported": True, "applied": {"temperature": 0, "seed": 0}}
    routes_file(tmp_path, monkeypatch, [mock("echo", "main.a", temperature=False, seed=False)])
    resp = client.generate(request(deterministic=True, generation={"temperature": 0.9}), config=Config.load())
    assert resp["determinism"] == {
        "requested": True,
        "supported": False,
        "applied": {"temperature": None, "seed": None},
    }


def test_cancellation(config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    routes_file(tmp_path, monkeypatch, [mock("slow-5000", "main.a")])
    cancel = threading.Event()
    threading.Timer(0.2, cancel.set).start()
    with pytest.raises(ModelError) as info:
        client.generate(request(), config=Config.load(), cancel=cancel)
    assert info.value.code == "CANCELLED"


def test_minimal_schema_instances() -> None:
    assert minimal({"type": "object", "required": ["a"], "properties": {"a": {"enum": ["x", "y"]}}}) == {"a": "x"}
    assert minimal({"type": "array", "items": {"type": "integer"}, "minItems": 2}) == [1, 1]


# Backend protocol -------------------------------------------------------------------------------------------


def backend_run(payload: Any) -> list[dict[str, Any]]:
    out = io.StringIO()
    assert backend.main(io.StringIO(json.dumps(payload) if not isinstance(payload, str) else payload), out) == 0
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_backend_streams_events_and_ends_with_the_response(config: Config) -> None:
    events = backend_run(
        {
            "model_api_version": "1.0",
            "request": request(stream=True, prompt="a b c"),
            "route": mock("echo", "main.a"),
            "context": {"deadline_ms": 5000},
        }
    )
    assert [e["seq"] for e in events] == list(range(len(events)))
    assert [e["type"] for e in events] == ["delta"] * 4 + ["usage", "end"]
    assert events[-1]["data"]["response"]["output"]["text"] == "echo: a b c"


def test_backend_errors_are_events_and_scrubbed(config: Config) -> None:
    events = backend_run({"model_api_version": "1.0", "request": request(), "route": mock("leak", "main.a")})
    assert events[-1]["type"] == "error" and events[-1]["data"]["error"]["code"] == "PROVIDER_ERROR"
    assert FAKE_SECRET not in json.dumps(events)
    bad = backend_run("not json")
    assert bad[-1]["data"]["error"]["code"] == "BACKEND_PROTOCOL_ERROR"


# CLI and configuration ---------------------------------------------------------------------------------------


def test_status_never_prints_credentials(config: Config, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "OPENAI_API_KEY             set" in out and FAKE_KEY not in out and FAKE_KEY[-4:] not in out


def test_ask_with_mock_routes(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    routes_file(tmp_path, monkeypatch, [mock("echo", "main.a")])
    assert cli.main(["ask", "hello", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["contract"] == "blux.model-response" and doc["output"]["text"] == "echo: hello"
    assert cli.main(["ask", "hello", "-m", "gpt-5-mini"]) == 0  # 1.0 lane name still works, mapped
    captured = capsys.readouterr()
    assert "1.0 vendor lane; using blux-main" in captured.err


def test_ask_failure_prints_the_normalized_error(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    routes_file(tmp_path, monkeypatch, [mock("fail-provider_auth_failed", "main.a")])
    assert cli.main(["ask", "x", "--json", "--no-history"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "ALL_ROUTES_FAILED"


def test_context_is_off_by_default_and_never_personal(
    config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from bluxgpt import context

    item = context.basic_context()
    assert str(Path.home()) not in item["content"] and str(Path.cwd()) not in item["content"]
    seen: list[dict[str, Any]] = []
    real = client.generate
    monkeypatch.setattr(client, "generate", lambda req, **kw: (seen.append(req), real(req, **kw))[1])
    routes_file(tmp_path, monkeypatch, [mock("echo", "main.a")])
    cli.main(["ask", "q", "--no-history"])
    cli.main(["ask", "q", "--context", "--no-history"])
    assert "context" not in seen[0] and seen[1]["context"][0]["kind"] == "environment"


def test_env_file_parsing() -> None:
    assert parse_env_file("# c\nexport A=1\nB='two words'\nC=x # note\nbad line\n") == {
        "A": "1",
        "B": "two words",
        "C": "x",
    }


def test_packaged_routes_cover_every_logical_model(config: Config) -> None:
    routes = client.load_routes(Config.load())
    assert set(routes["models"]) == {"blux-main", "blux-fast", "blux-reason", "blux-code"}
    assert all(
        r["provider"] in ("openai", "anthropic", "deepseek") for m in routes["models"].values() for r in m["routes"]
    )


def test_no_blux_shell_function_is_installed() -> None:
    script = (Path(cli.__file__).parent.parent / "scripts" / "install_shell.sh").read_text()
    assert "blux() {" not in script and "unfunction blux" in script
