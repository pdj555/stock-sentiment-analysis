"""Stock sentiment analysis package."""

from __future__ import annotations

__all__ = ["__version__", "DEFAULT_OPENAI_BASE_URL", "DEFAULT_OPENAI_MODEL"]

__version__ = "0.1.0"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
