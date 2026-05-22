from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from stock_sentiment import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL
from stock_sentiment.cache import JsonDiskCache
from stock_sentiment.errors import ConfigurationError, RemoteApiError
from stock_sentiment.google_rss import fetch_google_news_rss
from stock_sentiment.newsapi import fetch_everything
from stock_sentiment.sentiment import OpenAISentimentConfig, analyze_with_cache
from stock_sentiment.types import NewsArticle, SentimentSummary

SourceName = Literal["auto", "newsapi", "google-rss"]
WarnCallback = Callable[[str], None]


@dataclass(frozen=True)
class AnalysisRequest:
    ticker: str
    query: str | None = None
    lookback_days: int = 3
    max_articles: int = 25
    half_life_hours: float = 24.0
    source: SourceName = "auto"
    openai_api_key: str = ""
    newsapi_key: str = ""
    openai_model: str = DEFAULT_OPENAI_MODEL
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL
    use_cache: bool = True
    cache_ttl_hours: float = 24.0
    cache_dir: Path | None = None
    include_reasons: bool = False


@dataclass(frozen=True)
class AnalysisRunResult:
    summary: SentimentSummary
    articles: list[NewsArticle]
    source: SourceName
    lookback_days: int
    article_cap: int


def _default_warn(message: str) -> None:
    print(message, file=sys.stderr)


def display_source_name(source: str) -> str:
    if source == "newsapi":
        return "NewsAPI"
    if source == "google-rss":
        return "Google News RSS"
    return source


def default_cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "stock_sentiment"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "stock_sentiment"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "stock_sentiment"
    return Path.home() / ".cache" / "stock_sentiment"


def _require_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(f"{field_name} must be a string.")
    return value


def _validated_int(value: object, *, field_name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConfigurationError(f"{field_name} must be an integer >= {minimum}.")
    return value


def _validated_float(
    value: object,
    *,
    field_name: str,
    minimum: float,
    inclusive: bool,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        comparator = ">=" if inclusive else ">"
        raise ConfigurationError(f"{field_name} must be a number {comparator} {minimum:g}.")
    normalized = float(value)
    if inclusive:
        valid = normalized >= minimum
    else:
        valid = normalized > minimum
    if not valid:
        comparator = ">=" if inclusive else ">"
        raise ConfigurationError(f"{field_name} must be a number {comparator} {minimum:g}.")
    return normalized


def _validated_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{field_name} must be a boolean.")
    return value


def normalize_ticker(raw_ticker: object) -> str:
    ticker = _require_string(raw_ticker, field_name="Ticker").strip().upper()
    if not ticker:
        raise ConfigurationError("Ticker cannot be empty.")
    if any(ch.isspace() for ch in ticker):
        raise ConfigurationError("Ticker cannot contain whitespace.")
    if len(ticker) > 24:
        raise ConfigurationError("Ticker looks too long; expected a symbol like TSLA.")
    return ticker


def _normalize_query(raw_query: object | None, *, ticker: str) -> str:
    if raw_query is None:
        return ticker
    query = _require_string(raw_query, field_name="Query").strip()
    if not query:
        raise ConfigurationError("Query cannot be empty.")
    return query


def _validated_openai_config(request: AnalysisRequest) -> OpenAISentimentConfig:
    model = str(request.openai_model or "").strip()
    if not model:
        raise ConfigurationError("OpenAI model cannot be empty.")

    base_url = str(request.openai_base_url or "").strip()
    if not base_url:
        raise ConfigurationError("OpenAI base URL cannot be empty.")

    base_split = urlsplit(base_url)
    if base_split.scheme not in {"http", "https"} or not base_split.netloc:
        raise ConfigurationError(
            "OpenAI base URL must be an http(s) URL (e.g., https://api.openai.com/v1)."
        )

    return OpenAISentimentConfig(
        api_key=str(request.openai_api_key or "").strip(),
        model=model,
        base_url=base_url,
    )


def _fetch_google_news_rss_with_guidance(
    *,
    query: str,
    from_datetime: datetime,
    source_requested: SourceName,
    newsapi_key_present: bool,
) -> list[NewsArticle]:
    try:
        return fetch_google_news_rss(query=query, from_datetime=from_datetime)
    except RemoteApiError as e:
        lower = str(e).lower()
        parts: list[str] = []
        if any(
            token in lower
            for token in [
                "certificate verify failed",
                "timed out",
                "ssl",
                "failed (0)",
                "failed after retries",
                "network is unreachable",
                "connection reset",
                "connection refused",
            ]
        ):
            parts.append("Check your network connection or local TLS certificates.")
        if source_requested == "auto" and not newsapi_key_present:
            parts.append("Set NEWSAPI_KEY to let auto prefer NewsAPI.")
        guidance = f" {' '.join(parts)}" if parts else ""
        raise RemoteApiError(
            f"Google News RSS request failed.{guidance} Original error: {e}"
        ) from e


def _fetch_articles(
    *,
    query: str,
    from_datetime: datetime,
    source_requested: SourceName,
    newsapi_key: str,
    max_articles: int,
    warn: WarnCallback,
) -> tuple[SourceName, list[NewsArticle]]:
    source_used: SourceName = source_requested
    if source_used == "auto":
        source_used = "newsapi" if newsapi_key else "google-rss"

    if source_used == "newsapi":
        if not newsapi_key:
            raise ConfigurationError(
                "Missing NEWSAPI_KEY. Set it, or rerun with --source auto or --source google-rss."
            )
        try:
            return source_used, fetch_everything(
                api_key=newsapi_key,
                query=query,
                from_date=from_datetime.date().isoformat(),
                page_size=100,
                limit=max(1, max_articles),
            )
        except RemoteApiError as e:
            if source_requested != "auto":
                raise
            warn(f"NewsAPI request failed ({e}). Trying Google News RSS instead.")
            source_used = "google-rss"

    return source_used, _fetch_google_news_rss_with_guidance(
        query=query,
        from_datetime=from_datetime,
        source_requested=source_requested,
        newsapi_key_present=bool(newsapi_key),
    )


def _unique_articles(articles: list[NewsArticle], limit: int) -> list[NewsArticle]:
    unique: list[NewsArticle] = []
    seen: set[str] = set()
    for article in articles:
        key = article.url or article.article_id
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
        if len(unique) >= max(1, limit):
            break
    return unique


def run_analysis(
    request: AnalysisRequest,
    *,
    warn: WarnCallback | None = None,
) -> AnalysisRunResult:
    warn_callback = warn or _default_warn
    ticker = normalize_ticker(request.ticker)
    query = _normalize_query(request.query, ticker=ticker)

    lookback_days = _validated_int(
        request.lookback_days,
        field_name="Lookback days",
        minimum=1,
    )

    max_articles = _validated_int(
        request.max_articles,
        field_name="Max articles",
        minimum=1,
    )

    half_life_hours = _validated_float(
        request.half_life_hours,
        field_name="Half-life hours",
        minimum=0.0,
        inclusive=False,
    )

    source_requested = request.source
    if not isinstance(source_requested, str) or source_requested not in {
        "auto",
        "newsapi",
        "google-rss",
    }:
        raise ConfigurationError("Source must be auto, newsapi, or google-rss.")

    use_cache = _validated_bool(request.use_cache, field_name="Use cache")
    cache_ttl_hours = _validated_float(
        request.cache_ttl_hours,
        field_name="Cache TTL hours",
        minimum=0.0,
        inclusive=True,
    )

    openai = _validated_openai_config(request)
    newsapi_key = str(request.newsapi_key or "").strip()

    now = datetime.now(timezone.utc)
    from_datetime = now - timedelta(days=lookback_days)
    source_used, articles = _fetch_articles(
        query=query,
        from_datetime=from_datetime,
        source_requested=source_requested,
        newsapi_key=newsapi_key,
        max_articles=max_articles,
        warn=warn_callback,
    )
    unique_articles = _unique_articles(articles, max_articles)

    cache: JsonDiskCache | None = None
    ttl_seconds: float | None = None
    if use_cache:
        ttl_seconds = cache_ttl_hours * 3600.0
        try:
            cache = JsonDiskCache(
                request.cache_dir or default_cache_dir(),
                warn=warn_callback,
            )
        except OSError as e:
            cache = None
            ttl_seconds = None
            warn_callback(f"Cache disabled: {e}")

    if not openai.api_key and not use_cache and unique_articles:
        raise ConfigurationError(
            "Missing OLLAMA_API_KEY (or OPENAI_API_KEY). "
            "Set one to analyze articles, or rerun with caching enabled after a successful run."
        )

    try:
        summary = analyze_with_cache(
            ticker=ticker,
            query=query,
            articles=unique_articles,
            cache=cache,
            cache_ttl_seconds=ttl_seconds,
            openai=openai,
            include_reasons=bool(request.include_reasons),
            half_life_hours=half_life_hours,
        )
    except ConfigurationError as e:
        if not openai.api_key and (
            "OPENAI_API_KEY" in str(e) or "OLLAMA_API_KEY" in str(e)
        ):
            raise ConfigurationError(
                "Missing OLLAMA_API_KEY (or OPENAI_API_KEY). "
                "Some articles were not cached; set a key to analyze them."
            ) from e
        raise

    return AnalysisRunResult(
        summary=summary,
        articles=unique_articles,
        source=source_used,
        lookback_days=lookback_days,
        article_cap=max_articles,
    )
