from __future__ import annotations

import os

from stock_sentiment import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL
from stock_sentiment.errors import ConfigurationError

DEFAULT_OLLAMA_BASE_URL = "https://ollama.com/api"
DEFAULT_OLLAMA_MODEL = "gpt-oss:120b"


def resolve_openai_credentials() -> tuple[str, str, str]:
    """Return (api_key, base_url, model). OLLAMA_* wins over OPENAI_*."""

    ollama_key = os.environ.get("OLLAMA_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    api_key = ollama_key or openai_key
    if not api_key:
        raise ConfigurationError(
            "Missing OLLAMA_API_KEY (or OPENAI_API_KEY). "
            "Set one in your shell, ./.env, or GitHub Actions secrets."
        )

    if ollama_key:
        base_url = (
            os.environ.get("OLLAMA_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or DEFAULT_OLLAMA_BASE_URL
        )
        model = (
            os.environ.get("OLLAMA_MODEL")
            or os.environ.get("OPENAI_MODEL")
            or DEFAULT_OLLAMA_MODEL
        )
    else:
        base_url = os.environ.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
        model = os.environ.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL

    return api_key, base_url.rstrip("/"), model
