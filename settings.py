from __future__ import annotations

import os
from pathlib import Path

from stock_sentiment.env import load_dotenv


DEFAULT_DOTENV_PATH = Path(__file__).with_name(".env")

_DEFAULTS: dict[str, str] = {
    "NEWSAPI_KEY": "",
    "OPENAI_API_KEY": "",
    "OPENAI_MODEL": "gpt-4o-mini",
    "OPENAI_BASE_URL": "https://api.openai.com/v1",
}

__all__ = [
    "DEFAULT_DOTENV_PATH",
    "get_env",
    "load",
    "require_env",
    "NEWSAPI_KEY",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL",
]


def load(dotenv_path: Path | None = None) -> None:
    """
    Load environment variables from a .env file if present.

    This is intentionally non-destructive: it does not overwrite existing values.
    """

    load_dotenv(dotenv_path or DEFAULT_DOTENV_PATH)


def get_env(name: str, default: str | None = None) -> str | None:
    """
    Get an environment variable with an optional default.
    """

    if default is None:
        return os.environ.get(name)
    return os.environ.get(name, default)


def require_env(name: str) -> str:
    """
    Get a required environment variable or raise a clear error.
    """

    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def __getattr__(name: str) -> str:
    """
    Backward-compatible dynamic env access (e.g., settings.OPENAI_MODEL).
    """

    if name in _DEFAULTS:
        return os.environ.get(name, _DEFAULTS[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
