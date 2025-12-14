from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from stock_sentiment.cache import JsonDiskCache
from stock_sentiment.errors import ConfigurationError, ParseError
from stock_sentiment.openai_client import create_response, extract_output_text
from stock_sentiment.types import ArticleSentiment, NewsArticle, SentimentLabel, SentimentSummary, Signal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _recency_weight(*, published_at: datetime | None, half_life_hours: float) -> float:
    if published_at is None:
        return 1.0
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_seconds = max(0.0, (_utcnow() - published_at).total_seconds())
    half_life_seconds = max(1.0, half_life_hours * 3600.0)
    return 0.5 ** (age_seconds / half_life_seconds)


def _label_from_score(score: float, *, threshold: float = 0.15) -> SentimentLabel:
    if score > threshold:
        return "positive"
    if score < -threshold:
        return "negative"
    return "neutral"


def _signal_from_score(
    score: float,
    confidence: float,
    *,
    threshold: float = 0.15,
    min_confidence: float = 0.55,
) -> Signal:
    if confidence < min_confidence:
        return "hold"
    if score > threshold:
        return "buy"
    if score < -threshold:
        return "sell"
    return "hold"


def _truncate(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def _response_schema(include_reasons: bool) -> dict[str, Any]:
    result_properties: dict[str, Any] = {
        "article_id": {"type": "string"},
        "label": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "score": {"type": "number"},
        "confidence": {"type": "number"},
    }
    required = ["article_id", "label", "score", "confidence"]
    if include_reasons:
        result_properties["reason"] = {"type": "string"}
        required.append("reason")

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": result_properties,
                    "required": required,
                },
            }
        },
        "required": ["results"],
    }

    return {"type": "json_schema", "json_schema": {"name": "sentiment_results", "schema": schema, "strict": True}}


@dataclass(frozen=True)
class OpenAISentimentConfig:
    api_key: str
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.2
    max_output_tokens: int = 900
    timeout_seconds: float = 45.0
    max_retries: int = 6


def analyze_articles_with_openai(
    *,
    ticker: str,
    articles: list[NewsArticle],
    openai: OpenAISentimentConfig,
    include_reasons: bool = True,
) -> list[ArticleSentiment]:
    if not openai.api_key:
        raise ConfigurationError("Missing OPENAI_API_KEY")

    payload_articles: list[dict[str, Any]] = []
    for a in articles:
        payload_articles.append(
            {
                "article_id": a.article_id,
                "title": _truncate(a.title, 220),
                "description": _truncate(a.description, 900),
                "source": a.source,
                "published_at": a.published_at.isoformat() if a.published_at else None,
            }
        )

    system = (
        "You are a precise financial news sentiment engine. "
        "Classify each article's expected impact on the stock's price over the next 1-5 trading days. "
        "Use only the provided text. If unclear, choose neutral. "
        "Return the requested JSON only."
    )
    user = {
        "ticker": ticker,
        "instructions": {
            "label": "positive/negative/neutral price impact",
            "score": "number in [-1, 1] matching label sign; neutral should be 0",
            "confidence": "number in [0, 1]",
            "reason": "short justification (<= 20 words)" if include_reasons else None,
        },
        "articles": payload_articles,
    }

    input_payload = [
        {"role": "system", "content": [{"type": "text", "text": system}]},
        {"role": "user", "content": [{"type": "text", "text": json.dumps(user, ensure_ascii=False)}]},
    ]

    response = create_response(
        api_key=openai.api_key,
        model=openai.model,
        input_payload=input_payload,
        response_format=_response_schema(include_reasons),
        temperature=openai.temperature,
        max_output_tokens=openai.max_output_tokens,
        base_url=openai.base_url,
        timeout_seconds=openai.timeout_seconds,
        max_retries=openai.max_retries,
    )

    text = extract_output_text(response)
    if not text:
        raise ParseError("OpenAI response contained no output text")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ParseError(f"OpenAI output was not valid JSON: {e}") from e

    raw_results = parsed.get("results")
    if not isinstance(raw_results, list):
        raise ParseError("OpenAI output missing 'results' array")

    by_id: dict[str, ArticleSentiment] = {}
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        article_id = item.get("article_id")
        label = item.get("label")
        score = item.get("score")
        confidence = item.get("confidence")
        reason = item.get("reason") if include_reasons else None

        if not isinstance(article_id, str) or not article_id:
            continue
        if label not in {"positive", "negative", "neutral"}:
            continue
        if not isinstance(score, (int, float)) or not isinstance(confidence, (int, float)):
            continue
        if not math.isfinite(float(score)) or not math.isfinite(float(confidence)):
            continue

        normalized_score = float(_clamp(float(score), -1.0, 1.0))
        normalized_conf = float(_clamp(float(confidence), 0.0, 1.0))
        normalized_label: SentimentLabel = label  # type: ignore[assignment]

        if normalized_label == "neutral":
            normalized_score = 0.0
        elif normalized_label == "positive":
            normalized_score = abs(normalized_score)
        elif normalized_label == "negative":
            normalized_score = -abs(normalized_score)

        normalized_reason = None
        if include_reasons and isinstance(reason, str):
            normalized_reason = _truncate(reason, 140)

        by_id[article_id] = ArticleSentiment(
            article_id=article_id,
            label=normalized_label,
            score=normalized_score,
            confidence=normalized_conf,
            reason=normalized_reason,
        )

    results: list[ArticleSentiment] = []
    for article in articles:
        existing = by_id.get(article.article_id)
        if existing is None:
            results.append(
                ArticleSentiment(
                    article_id=article.article_id,
                    label="neutral",
                    score=0.0,
                    confidence=0.0,
                    reason="No classification returned" if include_reasons else None,
                )
            )
        else:
            results.append(existing)

    return results


def summarize_sentiment(
    *,
    ticker: str,
    query: str,
    results: list[ArticleSentiment],
    article_by_id: dict[str, NewsArticle],
    half_life_hours: float = 24.0,
) -> SentimentSummary:
    weights: list[float] = []
    weighted_scores: list[float] = []
    recency_weights: list[float] = []

    for r in results:
        article = article_by_id.get(r.article_id)
        recency = _recency_weight(
            published_at=article.published_at if article else None,
            half_life_hours=half_life_hours,
        )
        weight = recency * _clamp(r.confidence, 0.0, 1.0)
        weights.append(weight)
        recency_weights.append(recency)
        weighted_scores.append(r.score * weight)

    total_weight = sum(weights) if weights else 0.0
    score = sum(weighted_scores) / total_weight if total_weight > 0 else 0.0
    score = float(_clamp(score, -1.0, 1.0))

    total_recency = sum(recency_weights) if recency_weights else 0.0
    confidence = total_weight / total_recency if total_recency > 0 else 0.0
    confidence = float(_clamp(confidence, 0.0, 1.0))
    label = _label_from_score(score)

    return SentimentSummary(
        ticker=ticker,
        query=query,
        as_of=_utcnow(),
        score=score,
        label=label,
        confidence=confidence,
        signal=_signal_from_score(score, confidence),
        articles_analyzed=len(results),
        results=results,
    )


def analyze_with_cache(
    *,
    ticker: str,
    query: str,
    articles: list[NewsArticle],
    cache: JsonDiskCache | None,
    cache_ttl_seconds: float | None,
    openai: OpenAISentimentConfig,
    include_reasons: bool,
    batch_size: int = 20,
    half_life_hours: float = 24.0,
) -> SentimentSummary:
    article_by_id = {a.article_id: a for a in articles}

    cached_results: dict[str, ArticleSentiment] = {}
    to_analyze: list[NewsArticle] = []

    prompt_version_no_reasons = "openai_sentiment_v1"
    prompt_version_with_reasons = "openai_sentiment_v2"
    prompt_version = prompt_version_with_reasons if include_reasons else prompt_version_no_reasons

    def cache_key(prompt_version: str, article_id: str) -> str:
        base_url = openai.base_url.rstrip("/")
        temp = float(openai.temperature)
        max_tokens = int(openai.max_output_tokens)
        return f"{prompt_version}:{base_url}:{openai.model}:{temp:.6g}:{max_tokens}:{ticker}:{article_id}"

    def legacy_key(prompt_version: str, article_id: str) -> str:
        return f"{prompt_version}:{openai.model}:{ticker}:{article_id}"

    def parse_cached(article_id: str, value: Any, *, require_reason: bool) -> ArticleSentiment | None:
        if not isinstance(value, dict) or value.get("article_id") != article_id:
            return None

        label = value.get("label")
        if label not in {"positive", "negative", "neutral"}:
            return None
        normalized_label: SentimentLabel = label  # type: ignore[assignment]

        try:
            score = float(value.get("score"))
            confidence = float(value.get("confidence"))
        except (TypeError, ValueError):
            return None
        if not math.isfinite(score) or not math.isfinite(confidence):
            return None

        normalized_score = float(_clamp(score, -1.0, 1.0))
        normalized_confidence = float(_clamp(confidence, 0.0, 1.0))

        if normalized_label == "neutral":
            normalized_score = 0.0
        elif normalized_label == "positive":
            normalized_score = abs(normalized_score)
        elif normalized_label == "negative":
            normalized_score = -abs(normalized_score)

        reason = value.get("reason")
        if require_reason and (not isinstance(reason, str) or not reason.strip()):
            return None

        normalized_reason = None
        if isinstance(reason, str) and reason.strip():
            normalized_reason = _truncate(reason.strip(), 140)

        return ArticleSentiment(
            article_id=article_id,
            label=normalized_label,
            score=normalized_score,
            confidence=normalized_confidence,
            reason=normalized_reason,
        )

    for a in articles:
        primary_key = cache_key(prompt_version, a.article_id)
        candidates: list[tuple[str, bool]] = [
            (primary_key, include_reasons),
            (legacy_key(prompt_version, a.article_id), include_reasons),
        ]

        if include_reasons:
            candidates.extend(
                [
                    (cache_key(prompt_version_no_reasons, a.article_id), True),
                    (legacy_key(prompt_version_no_reasons, a.article_id), True),
                ]
            )
        else:
            candidates.extend(
                [
                    (cache_key(prompt_version_with_reasons, a.article_id), False),
                    (legacy_key(prompt_version_with_reasons, a.article_id), False),
                ]
            )

        cached_sentiment: ArticleSentiment | None = None
        used_key: str | None = None
        if cache:
            for key, require_reason in candidates:
                cached = cache.get(key, ttl_seconds=cache_ttl_seconds)
                cached_sentiment = parse_cached(a.article_id, cached, require_reason=require_reason)
                if cached_sentiment is not None:
                    used_key = key
                    break

        if cached_sentiment is not None:
            if cache and used_key and used_key != primary_key:
                cache.set(primary_key, cached_sentiment.to_dict())
            cached_results[a.article_id] = cached_sentiment
            continue

        to_analyze.append(a)

    fresh_results: list[ArticleSentiment] = []
    for i in range(0, len(to_analyze), max(1, batch_size)):
        batch = to_analyze[i : i + batch_size]
        fresh_results.extend(
            analyze_articles_with_openai(
                ticker=ticker, articles=batch, openai=openai, include_reasons=include_reasons
            )
        )

    if cache:
        for r in fresh_results:
            cache.set(cache_key(prompt_version, r.article_id), r.to_dict())

    fresh_by_id = {r.article_id: r for r in fresh_results}
    merged: list[ArticleSentiment] = []
    for a in articles:
        merged.append(
            cached_results.get(a.article_id)
            or fresh_by_id.get(a.article_id)
            or ArticleSentiment(
                article_id=a.article_id,
                label="neutral",
                score=0.0,
                confidence=0.0,
                reason=None,
            )
        )

    return summarize_sentiment(
        ticker=ticker,
        query=query,
        results=merged,
        article_by_id=article_by_id,
        half_life_hours=half_life_hours,
    )
