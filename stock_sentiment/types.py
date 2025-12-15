from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

SentimentLabel = Literal["positive", "negative", "neutral"]
Signal = Literal["buy", "sell", "hold"]


@dataclass(frozen=True)
class NewsArticle:
    article_id: str
    title: str
    description: str
    url: str | None
    source: str | None
    published_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


@dataclass(frozen=True)
class ArticleSentiment:
    article_id: str
    label: SentimentLabel
    score: float  # [-1, 1]
    confidence: float  # [0, 1]
    reason: str | None = None

    def to_dict(self, *, include_reason: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "article_id": self.article_id,
            "label": self.label,
            "score": self.score,
            "confidence": self.confidence,
        }
        if include_reason:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class SentimentSummary:
    ticker: str
    query: str
    as_of: datetime
    score: float
    label: SentimentLabel
    confidence: float
    signal: Signal
    articles_analyzed: int
    results: list[ArticleSentiment]

    def to_dict(self, *, include_reasons: bool = True) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "query": self.query,
            "as_of": self.as_of.isoformat(),
            "score": self.score,
            "label": self.label,
            "confidence": self.confidence,
            "signal": self.signal,
            "articles_analyzed": self.articles_analyzed,
            "results": [r.to_dict(include_reason=include_reasons) for r in self.results],
        }
