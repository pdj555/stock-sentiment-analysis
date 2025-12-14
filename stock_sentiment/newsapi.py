from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from stock_sentiment.http import http_request_json
from stock_sentiment.types import NewsArticle


def _stable_article_id(*parts: str) -> str:
    joined = "|".join(p.strip() for p in parts if p is not None)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _parse_published_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        # Treat naive datetimes as UTC to avoid mixing aware/naive downstream.
        return dt.replace(tzinfo=timezone.utc)
    return dt


def fetch_everything(
    *,
    api_key: str,
    query: str,
    from_date: str | None = None,
    to_date: str | None = None,
    language: str = "en",
    sort_by: str = "publishedAt",
    page_size: int = 50,
    page: int = 1,
    timeout_seconds: float = 30.0,
) -> list[NewsArticle]:
    """
    Fetch articles from NewsAPI /v2/everything.

    Dates use ISO-8601 or YYYY-MM-DD per NewsAPI.
    """

    params: dict[str, Any] = {
        "q": query,
        "language": language,
        "sortBy": sort_by,
        "pageSize": page_size,
        "page": page,
    }
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    url = f"https://newsapi.org/v2/everything?{urlencode(params)}"
    data = http_request_json(
        method="GET",
        url=url,
        headers={"x-api-key": api_key},
        timeout_seconds=timeout_seconds,
    )

    articles: list[NewsArticle] = []
    for raw in data.get("articles", []) or []:
        if not isinstance(raw, dict):
            continue

        title = (raw.get("title") or "").strip()
        description = (raw.get("description") or "").strip()
        url_value = raw.get("url")
        url_str = url_value.strip() if isinstance(url_value, str) and url_value.strip() else None

        source_name = None
        source_raw = raw.get("source")
        if isinstance(source_raw, dict) and isinstance(source_raw.get("name"), str):
            source_name = source_raw["name"].strip() or None

        published_at = _parse_published_at(raw.get("publishedAt"))
        article_id = _stable_article_id(url_str or "", title, str(published_at or ""))

        if not title and not description:
            continue

        articles.append(
            NewsArticle(
                article_id=article_id,
                title=title,
                description=description,
                url=url_str,
                source=source_name,
                published_at=published_at,
            )
        )

    return articles
