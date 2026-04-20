from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


CONFIG_DIR = Path.home() / ".config" / "bluxgpt"
ENV_PATH = CONFIG_DIR / ".env"


@dataclass
class Settings:
    default_model: str
    cheap_model: str
    fast_model: str
    openai_api_key: str
    openai_model: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    anthropic_api_key: str
    anthropic_model: str
    stream: bool
    context_inject: bool
    log_requests: bool
    axiom_logging: bool


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)

    return Settings(
        default_model=os.getenv("BLUXGPT_DEFAULT_MODEL", "gpt-5-mini"),
        cheap_model=os.getenv("BLUXGPT_CHEAP_MODEL", "deepseek-r2"),
        fast_model=os.getenv("BLUXGPT_FAST_MODEL", "claude-haiku-4.5"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-r2"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
        stream=_truthy(os.getenv("BLUXGPT_STREAM"), True),
        context_inject=_truthy(os.getenv("BLUXGPT_CONTEXT_INJECT"), True),
        log_requests=_truthy(os.getenv("BLUXGPT_LOG_REQUESTS"), True),
        axiom_logging=_truthy(os.getenv("BLUXGPT_AXIOM_LOGGING"), True),
    )
