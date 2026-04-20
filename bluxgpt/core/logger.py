from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json
import os

LOG_DIR = Path.home() / ".config" / "bluxgpt" / "logs"


def _safe_tail(value: str) -> str:
    """Return masked key: only last 4 chars visible."""
    if not value:
        return ""
    return f"****{value[-4:]}"


def _axiom_runs_dir() -> Optional[Path]:
    """Return AXIOM's runs directory if AXIOM is present and logging is enabled."""
    axiom_ready = os.getenv("AXIOM_READY", "0") == "1"
    axiom_root = os.getenv("AXIOM_REPO_ROOT", "")
    if not axiom_ready or not axiom_root:
        return None
    runs = Path(axiom_root) / "cockpit" / "runs"
    if runs.is_dir():
        return runs
    return None


def log_request(model: str, prompt: str, response: str) -> None:
    """Write request/response log to BluxGPT local logs and optionally AXIOM runs."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Use timezone-aware datetime (utcnow is deprecated in 3.12+)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d_%H%M%S")

    payload = {
        "timestamp": now.isoformat(),
        "model": model,
        "prompt": prompt,
        "response": response,
        "env": {
            "BLUX10K_VERSION": os.getenv("BLUX10K_VERSION", ""),
            "AXIOM_VERSION": os.getenv("AXIOM_VERSION", ""),
            "BLUXGPT_VERSION": os.getenv("BLUXGPT_VERSION", "1.0.0"),
            "OPENAI_API_KEY": _safe_tail(os.getenv("OPENAI_API_KEY", "")),
            "DEEPSEEK_API_KEY": _safe_tail(os.getenv("DEEPSEEK_API_KEY", "")),
            "ANTHROPIC_API_KEY": _safe_tail(os.getenv("ANTHROPIC_API_KEY", "")),
        },
    }

    # Local BluxGPT log
    local_path = LOG_DIR / f"{stamp}_query.json"
    local_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # AXIOM run logging
    axiom_runs = _axiom_runs_dir()
    if axiom_runs is not None:
        run_dir = axiom_runs / f"{stamp}_ai_bluxgpt"
        run_dir.mkdir(parents=True, exist_ok=True)

        # output.log — plain text response
        (run_dir / "output.log").write_text(response, encoding="utf-8")

        # metadata.json — AXIOM-compatible format
        metadata = {
            "mode": "ai",
            "action": "bluxgpt",
            "command": f"blux ask (model={model})",
            "exit_code": "0",
            "platform": os.getenv("BLUXGPT_PLATFORM", ""),
            "cwd": os.getcwd(),
            "started_at": now.isoformat(),
            "ended_at": now.isoformat(),
            "model": model,
            "bluxgpt_version": os.getenv("BLUXGPT_VERSION", "1.0.0"),
        }
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
