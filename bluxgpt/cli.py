"""`bluxgpt`: advisory CLI and BLUX model backend.

  bluxgpt ask "question" [-m blux-main|blux-fast|blux-reason|blux-code] [--stream] [--json] ...
  bluxgpt models | status | check [--real] | history | version | uninstall
  bluxgpt blux-model-backend        (used by BLUX; speaks the model-backend protocol on stdin/stdout)

BluxGPT is advisory: it prints answers and tool calls, and never runs anything. Exit codes: 0 ok, 1 the
model call failed (the normalized error is printed), 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path
from typing import Any

from bluxgpt import __version__, client, history
from bluxgpt.api import LOGICAL_MODELS, MODEL_API_VERSION, ModelError
from bluxgpt.config import SECRET_NAMES, Config
from bluxgpt.context import SYSTEM_PROMPT, basic_context

OVERLAY_START = "### >>> BLUXGPT OVERLAY >>>"
OVERLAY_END = "### <<< BLUXGPT OVERLAY <<<"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bluxgpt", description="BluxGPT: advisory AI CLI and BLUX model gateway.")
    p.add_argument("--version", action="version", version=f"bluxgpt {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("ask", help="ask a logical BLUX model (advisory only)")
    a.add_argument("prompt")
    a.add_argument("-m", "--model", help="blux-main (default), blux-fast, blux-reason or blux-code")
    a.add_argument("--system", help="system instructions (replaces the BluxGPT default)")
    a.add_argument("--context", action="store_true", help="add basic environment context (platform, tool versions)")
    a.add_argument("--json-schema", help="JSON Schema file: return structured output matching it")
    a.add_argument("--stream", action="store_true", help="print the answer as it arrives")
    a.add_argument("--deterministic", action="store_true", help="temperature 0 / fixed seed where the route allows")
    a.add_argument("--max-output-tokens", type=int)
    a.add_argument("--timeout", type=float, default=120.0, help="seconds (default 120)")
    a.add_argument("--no-fallback", action="store_true")
    a.add_argument("--json", action="store_true", help="print the full blux.model-response")
    a.add_argument("--no-history", action="store_true")
    m = sub.add_parser("models", help="logical models and the routes that serve them")
    m.add_argument("--json", action="store_true")
    sub.add_parser("status", help="configuration: which keys are set (never their values), routes, flags")
    c = sub.add_parser("check", help="check routes: offline with the mock provider, or --real against providers")
    c.add_argument(
        "--real", action="store_true", help="send a tiny prompt to every configured real route (uses credit)"
    )
    c.add_argument("--model", choices=LOGICAL_MODELS)
    h = sub.add_parser("history", help="local history")
    h.add_argument("--limit", type=int, default=20)
    h.add_argument("--clear", action="store_true")
    h.add_argument("--json", action="store_true")
    sub.add_parser("version", help="print the version")
    sub.add_parser("uninstall", help="remove the BLUXGPT OVERLAY block from ~/.zshrc.local")
    sub.add_parser("blux-model-backend", help="BLUX model-backend protocol (JSON on stdin, event lines on stdout)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "blux-model-backend":
        from bluxgpt.backend import main as backend

        return backend()
    config = Config.load()
    if args.command == "version":
        print(f"bluxgpt {__version__} (BLUX Model API {MODEL_API_VERSION})")
        return 0
    if args.command == "ask":
        return _ask(args, config)
    if args.command == "models":
        routes = client.load_routes(config)
        if args.json:
            print(json.dumps(routes, indent=2))
            return 0
        print(f"routes: {routes['routes_id']}")
        for model in LOGICAL_MODELS:
            print(f"\n{model}")
            for r in routes["models"][model]["routes"]:
                print(
                    f"  {r['route_id']:<18} {r['provider']}/{r['provider_model']}  [{r['tier']}]  "
                    f"{', '.join(r['capabilities'])}"
                )
        return 0
    if args.command == "status":
        default, note = config.default_model()
        print(f"bluxgpt {__version__}  config {config.path} ({'found' if config.file else 'not found'})")
        print(f"default model  {default}" + (f"   ({note})" if note else ""))
        print(f"routes         {config.get('BLUXGPT_ROUTES') or 'packaged default'}")
        print("credentials    (presence only; values are never shown)")
        for name in SECRET_NAMES:
            print(f"  {name:<26} {'set' if config.secret(name) else 'missing'}")
        print(f"history        {'on' if config.flag('BLUXGPT_HISTORY', True) else 'off'}")
        print(f"context        {config.get('BLUXGPT_CONTEXT', 'off')}")
        return 0
    if args.command == "check":
        return _check(args, config)
    if args.command == "history":
        if args.clear:
            history.clear()
            print("history cleared")
            return 0
        entries = history.read(args.limit)
        if args.json:
            print(json.dumps(entries, indent=2, ensure_ascii=False))
        for e in [] if args.json else entries:
            print(f"{e.get('timestamp', '')[:19]}  {e.get('model')} via {e.get('route')}")
            print(f"  Q: {e.get('prompt', '')[:120]}")
            print(f"  A: {e.get('response', '')[:200]}\n")
        return 0
    if args.command == "uninstall":
        return _uninstall()
    raise AssertionError(args.command)  # pragma: no cover


def _ask(args: argparse.Namespace, config: Config) -> int:
    model = args.model
    if model is None:
        model, note = config.default_model()
        if note:
            print(f"bluxgpt: {note}", file=sys.stderr)
    elif model not in LOGICAL_MODELS:
        from bluxgpt.config import LEGACY_MODELS

        if model in LEGACY_MODELS:
            print(f"bluxgpt: '{model}' is a 1.0 vendor lane; using {LEGACY_MODELS[model]}", file=sys.stderr)
            model = LEGACY_MODELS[model]
    request: dict[str, Any] = {
        "contract": "blux.model-request",
        "model_api_version": MODEL_API_VERSION,
        "model": model,
        "system": args.system or SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": args.prompt}],
        "timeout_ms": int(args.timeout * 1000),
        "client": {"name": "bluxgpt", "version": __version__},
    }
    if args.context or config.get("BLUXGPT_CONTEXT") == "basic":
        request["context"] = [basic_context()]
    if args.json_schema:
        request["response_format"] = {
            "type": "json_schema",
            "name": "output",
            "schema": json.loads(Path(args.json_schema).read_text(encoding="utf-8")),
        }
    if args.stream:
        request["stream"] = True
    if args.deterministic:
        request["deterministic"] = True
    if args.max_output_tokens:
        request["generation"] = {"max_output_tokens": args.max_output_tokens}
    if args.no_fallback:
        request["routing"] = {"allow_fallback": False}
    streamed = []

    def on_event(kind: str, data: dict[str, Any]) -> None:
        if kind == "delta" and args.stream and not args.json:
            streamed.append(data["text"])
            sys.stdout.write(data["text"])
            sys.stdout.flush()

    cancel = threading.Event()
    try:
        resp = client.generate(request, config=config, on_event=on_event, cancel=cancel)
    except KeyboardInterrupt:
        cancel.set()
        print("\nbluxgpt: cancelled", file=sys.stderr)
        return 1
    except ModelError as exc:
        print(json.dumps(exc.to_document(), indent=2), file=sys.stdout if args.json else sys.stderr)
        return 1
    out = resp["output"]
    answer = out["text"] if out["json"] is None else json.dumps(out["json"], indent=2, ensure_ascii=False)
    if args.json:
        print(json.dumps(resp, indent=2, ensure_ascii=False))
    else:
        if streamed:
            print()
        elif answer:
            print(answer)
        for call in out["tool_calls"]:
            print(f"[tool call, not executed] {call['name']}({json.dumps(call['arguments'])})")
        routing = resp["routing"]
        note = " (fallback)" if routing["fallback_used"] or routing["degraded"] else ""
        print(
            f"-- {resp['model']} via {resp['provider']['provider']}/{resp['provider']['provider_model']}{note}",
            file=sys.stderr,
        )
    if config.flag("BLUXGPT_HISTORY", True) and not args.no_history:
        history.append(resp["model"], resp["routing"]["route_id"], args.prompt, answer or "")
    return 0


def _check(args: argparse.Namespace, config: Config) -> int:
    from bluxgpt.gateway import Gateway

    gateway = Gateway(config)
    routes = client.load_routes(config)
    models = [args.model] if args.model else list(LOGICAL_MODELS)
    failed = 0
    seen: set[tuple[str, str]] = set()
    for model in models:
        for route in routes["models"][model]["routes"]:
            key = (route["provider"], route["provider_model"])
            if key in seen:
                continue
            seen.add(key)
            mocked = route["provider"] == "mock"
            if not args.real and not mocked:
                print(
                    f"SKIP  {route['route_id']:<18} {route['provider']}/{route['provider_model']}  (real; use --real)"
                )
                continue
            request = {
                "contract": "blux.model-request",
                "model_api_version": MODEL_API_VERSION,
                "model": model,
                "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
                "generation": {"max_output_tokens": 400},
            }
            import time

            try:
                resp = gateway.generate(
                    request,
                    route,
                    deadline=time.monotonic() + 60,
                    cancel=threading.Event(),
                    emit=lambda kind, data: None,
                )
                u = resp["usage"]
                print(
                    f"OK    {route['route_id']:<18} {route['provider']}/{route['provider_model']}  "
                    f"[{'MOCK' if mocked else 'REAL'}] {resp['finish_reason']} tokens={u['total_tokens']}"
                )
            except ModelError as exc:
                failed += 1
                print(
                    f"FAIL  {route['route_id']:<18} {route['provider']}/{route['provider_model']}  "
                    f"[{'MOCK' if mocked else 'REAL'}] {exc.code}: {exc.message}"
                )
    return 1 if failed else 0


def _uninstall() -> int:
    import shutil

    target = Path.home() / ".zshrc.local"
    if not target.exists() or OVERLAY_START not in target.read_text(encoding="utf-8"):
        print("BLUXGPT OVERLAY not found in ~/.zshrc.local; nothing to do")
        return 0
    shutil.copy2(target, target.with_suffix(".local.bak"))
    keep, skip = [], False
    for line in target.read_text(encoding="utf-8").splitlines(keepends=True):
        if line.rstrip() == OVERLAY_START:
            skip = True
        elif line.rstrip() == OVERLAY_END:
            skip = False
        elif not skip:
            keep.append(line)
    target.write_text("".join(keep), encoding="utf-8")
    print("BLUXGPT OVERLAY removed from ~/.zshrc.local (backup: ~/.zshrc.local.bak)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
