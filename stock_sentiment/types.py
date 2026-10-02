from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

SentimentLabel = Literal["positive", "negative", "neutral"]
Signal = Literal["buy", "sell", "hold"]
EvidenceGrade = Literal["limited", "moderate", "strong"]
EvidenceDirection = Literal["positive", "negative"]


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
    classified: bool = True

    def to_dict(self, *, include_reason: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "article_id": self.article_id,
            "label": self.label,
            "score": self.score,
            "confidence": self.confidence,
            "classified": self.classified,
        }
        if include_reason:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class EvidenceDriver:
    article_id: str
    title: str
    url: str | None
    source: str | None
    published_at: datetime | None
    direction: EvidenceDirection
    impact: float
    confidence: float
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat()
            if self.published_at
            else None,
            "direction": self.direction,
            "impact": self.impact,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class EvidenceProfile:
    grade: EvidenceGrade
    coverage: float
    agreement: float
    classified_articles: int
    total_articles: int
    drivers: tuple[EvidenceDriver, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "grade": self.grade,
            "coverage": self.coverage,
            "agreement": self.agreement,
            "classified_articles": self.classified_articles,
            "total_articles": self.total_articles,
            "drivers": [driver.to_dict() for driver in self.drivers],
        }


def empty_evidence_profile() -> EvidenceProfile:
    return EvidenceProfile(
        grade="limited",
        coverage=0.0,
        agreement=0.0,
        classified_articles=0,
        total_articles=0,
        drivers=(),
    )


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
    classification_degraded: bool = False
    classification_warnings: tuple[str, ...] = ()
    evidence: EvidenceProfile = field(default_factory=empty_evidence_profile)

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
            "classification_degraded": self.classification_degraded,
            "classification_warnings": list(self.classification_warnings),
            "evidence": self.evidence.to_dict(),
            "results": [r.to_dict(include_reason=include_reasons) for r in self.results],
        }
