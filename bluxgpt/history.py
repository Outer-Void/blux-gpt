"""Local question/answer history (~/.config/bluxgpt/history.jsonl). It stays on this machine.

Set BLUXGPT_HISTORY=0 or pass --no-history to keep nothing. Entries hold the logical model, the route that
served it, the question and the answer; never credentials.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_FILE = Path.home() / ".config" / "bluxgpt" / "history.jsonl"


def append(model: str, route_id: str, prompt: str, answer: str, path: Path = HISTORY_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "route": route_id,
        "prompt": prompt,
        "response": answer,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read(limit: int = 20, path: Path = HISTORY_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out[-limit:]


def clear(path: Path = HISTORY_FILE) -> None:
    if path.exists():
        path.write_text("", encoding="utf-8")
