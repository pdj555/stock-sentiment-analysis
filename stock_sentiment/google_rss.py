from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode

from stock_sentiment.errors import ParseError
from stock_sentiment.http import http_request_bytes
from stock_sentiment.types import NewsArticle


_TAG_RE = re.compile(r"<[^>]+>")


def _stable_article_id(*parts: str) -> str:
    joined = "|".join(p.strip() for p in parts if p is not None)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _clean_html(text: str) -> str:
    without_tags = _TAG_RE.sub("", text)
    return html.unescape(" ".join(without_tags.split())).strip()


def _parse_pubdate(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def fetch_google_news_rss(
    *,
    query: str,
    hl: str = "en-US",
    gl: str = "US",
    ceid: str = "US:en",
    from_datetime: datetime | None = None,
    timeout_seconds: float = 20.0,
) -> list[NewsArticle]:
    """
    Fetch articles from Google News RSS (no API key required).

    This is a lightweight fallback when NewsAPI isn't configured.
    """

    params = {"q": query, "hl": hl, "gl": gl, "ceid": ceid}
    url = f"https://news.google.com/rss/search?{urlencode(params)}"

    body = http_request_bytes(method="GET", url=url, timeout_seconds=timeout_seconds)

    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise ParseError(f"Google News RSS returned invalid XML: {e}") from e
    articles: list[NewsArticle] = []

    if from_datetime is not None and from_datetime.tzinfo is None:
        from_datetime = from_datetime.replace(tzinfo=timezone.utc)

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip() or None
        description_raw = item.findtext("description") or ""
        description = _clean_html(description_raw)
        source = (item.findtext("source") or "").strip() or None
        published_at = _parse_pubdate(item.findtext("pubDate"))

        if from_datetime is not None and published_at is not None and published_at < from_datetime:
            continue

        if not title and not description:
            continue

        article_id = _stable_article_id(link or "", title, str(published_at or ""))
        articles.append(
            NewsArticle(
                article_id=article_id,
                title=title,
                description=description,
                url=link,
                source=source,
                published_at=published_at,
            )
        )

    return articles
