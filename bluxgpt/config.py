"""Configuration: ~/.config/bluxgpt/.env (or $BLUXGPT_CONFIG) and the environment.

The file is KEY=VALUE lines (`export` and quotes allowed). Environment variables win over the file.
Secrets are read on demand and never printed, logged or returned, not even partially.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path.home() / ".config" / "bluxgpt" / ".env"
SECRET_NAMES = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_COMPATIBLE_API_KEY")
# BluxGPT 1.0 lane values -> logical models
LEGACY_MODELS = {
    "gpt-5-mini": "blux-main",
    "claude-haiku-4.5": "blux-fast",
    "deepseek-chat": "blux-fast",
    "deepseek-reasoner": "blux-reason",
    "openai": "blux-main",
    "gpt": "blux-main",
    "claude": "blux-fast",
    "haiku": "blux-fast",
    "fast": "blux-fast",
    "deepseek": "blux-fast",
    "cheap": "blux-fast",
    "reasoner": "blux-reason",
    "reason": "blux-reason",
    "code": "blux-code",
    "main": "blux-main",
}


def parse_env_file(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        out[key.strip()] = value
    return out


@dataclass
class Config:
    path: Path
    file: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        p = Path(path or os.environ.get("BLUXGPT_CONFIG") or DEFAULT_PATH)
        try:
            file = parse_env_file(p.read_text(encoding="utf-8"))
        except OSError:
            file = {}
        return cls(p, file)

    def get(self, name: str, default: str = "") -> str:
        return os.environ.get(name) or self.file.get(name) or default

    def secret(self, name: str | None) -> str | None:
        if not name:
            return None
        return self.get(name) or None

    def flag(self, name: str, default: bool) -> bool:
        value = self.get(name)
        return default if not value else value.strip().lower() in ("1", "true", "yes", "on")

    def default_model(self) -> tuple[str, str | None]:
        """The default logical model, and a deprecation note if a 1.0 vendor lane was configured."""
        value = self.get("BLUXGPT_DEFAULT_MODEL", "blux-main")
        if value in LEGACY_MODELS:
            return LEGACY_MODELS[
                value
            ], f"BLUXGPT_DEFAULT_MODEL={value} is a 1.0 vendor lane; use {LEGACY_MODELS[value]}"
        return value, None
