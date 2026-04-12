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


def _parse_article(raw: Any) -> NewsArticle | None:
    if not isinstance(raw, dict):
        return None

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
        return None

    return NewsArticle(
        article_id=article_id,
        title=title,
        description=description,
        url=url_str,
        source=source_name,
        published_at=published_at,
    )


def _request_everything_page(
    *,
    api_key: str,
    query: str,
    from_date: str | None,
    to_date: str | None,
    language: str,
    sort_by: str,
    page_size: int,
    page: int,
    timeout_seconds: float,
) -> list[NewsArticle]:
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
        article = _parse_article(raw)
        if article is not None:
            articles.append(article)
    return articles


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
    limit: int | None = None,
    timeout_seconds: float = 30.0,
) -> list[NewsArticle]:
    """
    Fetch articles from NewsAPI /v2/everything.

    Dates use ISO-8601 or YYYY-MM-DD per NewsAPI.
    """

    normalized_page_size = max(1, min(int(page_size), 100))
    normalized_page = max(1, int(page))

    if limit is None:
        return _request_everything_page(
            api_key=api_key,
            query=query,
            from_date=from_date,
            to_date=to_date,
            language=language,
            sort_by=sort_by,
            page_size=normalized_page_size,
            page=normalized_page,
            timeout_seconds=timeout_seconds,
        )

    target_limit = max(1, int(limit))
    articles: list[NewsArticle] = []
    seen: set[str] = set()
    next_page = normalized_page

    while len(articles) < target_limit:
        remaining = target_limit - len(articles)
        request_page_size = min(normalized_page_size, remaining)
        page_articles = _request_everything_page(
            api_key=api_key,
            query=query,
            from_date=from_date,
            to_date=to_date,
            language=language,
            sort_by=sort_by,
            page_size=request_page_size,
            page=next_page,
            timeout_seconds=timeout_seconds,
        )

        for article in page_articles:
            dedupe_key = article.url or article.article_id
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            articles.append(article)
            if len(articles) >= target_limit:
                break

        if len(page_articles) < request_page_size:
            break
        next_page += 1

    return articles
