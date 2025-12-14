from __future__ import annotations


class StockSentimentError(Exception):
    """Base exception for this project."""


class ConfigurationError(StockSentimentError):
    """Raised when required configuration is missing or invalid."""


class RemoteApiError(StockSentimentError):
    """Raised when a remote API request fails."""


class ParseError(StockSentimentError):
    """Raised when a response cannot be parsed or validated."""

