from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
import json

HISTORY_DIR = Path.home() / ".config" / "bluxgpt"
HISTORY_FILE = HISTORY_DIR / "history.jsonl"


def ensure_history_dir() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def append_history(model: str, prompt: str, response: str) -> None:
    ensure_history_dir()
    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt": prompt,
        "response": response,
    }
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_history(limit: int = 20) -> List[Dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries[-limit:]


def clear_history() -> None:
    ensure_history_dir()
    HISTORY_FILE.write_text("", encoding="utf-8")
