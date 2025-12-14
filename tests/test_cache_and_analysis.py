from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from stock_sentiment.cache import JsonDiskCache
from stock_sentiment.sentiment import OpenAISentimentConfig, analyze_with_cache
from stock_sentiment.types import ArticleSentiment, NewsArticle


class TestCacheAndAnalysis(unittest.TestCase):
    def test_json_disk_cache_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = JsonDiskCache(Path(tmp))
            cache.set("k", {"a": 1})
            self.assertEqual(cache.get("k", ttl_seconds=60), {"a": 1})

    def test_analyze_with_cache_avoids_repeated_openai_calls(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        articles = [
            NewsArticle(
                article_id="a1",
                title="Good news",
                description="Profits up",
                url="https://example.com/1",
                source="Example",
                published_at=now,
            ),
            NewsArticle(
                article_id="a2",
                title="Bad news",
                description="Investigation announced",
                url="https://example.com/2",
                source="Example",
                published_at=now,
            ),
        ]

        fake_results = [
            ArticleSentiment(article_id="a1", label="positive", score=0.7, confidence=0.9, reason="earnings beat"),
            ArticleSentiment(article_id="a2", label="negative", score=-0.6, confidence=0.8, reason="legal risk"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            cache = JsonDiskCache(Path(tmp))
            openai = OpenAISentimentConfig(api_key="test", model="test-model")

            with patch(
                "stock_sentiment.sentiment.analyze_articles_with_openai", return_value=fake_results
            ) as mocked:
                analyze_with_cache(
                    ticker="TSLA",
                    query="TSLA",
                    articles=articles,
                    cache=cache,
                    cache_ttl_seconds=3600,
                    openai=openai,
                    include_reasons=True,
                )
                self.assertEqual(mocked.call_count, 1)

                analyze_with_cache(
                    ticker="TSLA",
                    query="TSLA",
                    articles=articles,
                    cache=cache,
                    cache_ttl_seconds=3600,
                    openai=openai,
                    include_reasons=True,
                )
                self.assertEqual(mocked.call_count, 1)

    def test_analyze_with_cache_refreshes_when_reasons_are_requested(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        articles = [
            NewsArticle(
                article_id="a1",
                title="Good news",
                description="Profits up",
                url="https://example.com/1",
                source="Example",
                published_at=now,
            ),
            NewsArticle(
                article_id="a2",
                title="Bad news",
                description="Investigation announced",
                url="https://example.com/2",
                source="Example",
                published_at=now,
            ),
        ]

        no_reason_results = [
            ArticleSentiment(article_id="a1", label="positive", score=0.7, confidence=0.9),
            ArticleSentiment(article_id="a2", label="negative", score=-0.6, confidence=0.8),
        ]
        reason_results = [
            ArticleSentiment(article_id="a1", label="positive", score=0.7, confidence=0.9, reason="earnings beat"),
            ArticleSentiment(article_id="a2", label="negative", score=-0.6, confidence=0.8, reason="legal risk"),
        ]

        def fake_analyze(*, include_reasons: bool, **_: object) -> list[ArticleSentiment]:
            return reason_results if include_reasons else no_reason_results

        with tempfile.TemporaryDirectory() as tmp:
            cache = JsonDiskCache(Path(tmp))
            openai = OpenAISentimentConfig(api_key="test", model="test-model")

            with patch("stock_sentiment.sentiment.analyze_articles_with_openai", side_effect=fake_analyze) as mocked:
                analyze_with_cache(
                    ticker="TSLA",
                    query="TSLA",
                    articles=articles,
                    cache=cache,
                    cache_ttl_seconds=3600,
                    openai=openai,
                    include_reasons=False,
                )
                analyze_with_cache(
                    ticker="TSLA",
                    query="TSLA",
                    articles=articles,
                    cache=cache,
                    cache_ttl_seconds=3600,
                    openai=openai,
                    include_reasons=True,
                )
                analyze_with_cache(
                    ticker="TSLA",
                    query="TSLA",
                    articles=articles,
                    cache=cache,
                    cache_ttl_seconds=3600,
                    openai=openai,
                    include_reasons=True,
                )

                self.assertEqual(mocked.call_count, 2)
                self.assertFalse(mocked.call_args_list[0].kwargs["include_reasons"])
                self.assertTrue(mocked.call_args_list[1].kwargs["include_reasons"])

    def test_analyze_with_cache_can_reuse_reasoned_cache_without_reasons(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        articles = [
            NewsArticle(
                article_id="a1",
                title="Good news",
                description="Profits up",
                url="https://example.com/1",
                source="Example",
                published_at=now,
            )
        ]

        reason_results = [
            ArticleSentiment(article_id="a1", label="positive", score=0.7, confidence=0.9, reason="earnings beat"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            cache = JsonDiskCache(Path(tmp))
            openai = OpenAISentimentConfig(api_key="test", model="test-model")

            with patch("stock_sentiment.sentiment.analyze_articles_with_openai", return_value=reason_results) as mocked:
                analyze_with_cache(
                    ticker="TSLA",
                    query="TSLA",
                    articles=articles,
                    cache=cache,
                    cache_ttl_seconds=3600,
                    openai=openai,
                    include_reasons=True,
                )
                analyze_with_cache(
                    ticker="TSLA",
                    query="TSLA",
                    articles=articles,
                    cache=cache,
                    cache_ttl_seconds=3600,
                    openai=openai,
                    include_reasons=False,
                )

                self.assertEqual(mocked.call_count, 1)

    def test_analyze_with_cache_normalizes_cached_score_sign(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        articles = [
            NewsArticle(
                article_id="a1",
                title="Good news",
                description="Profits up",
                url="https://example.com/1",
                source="Example",
                published_at=now,
            )
        ]

        cached = {"article_id": "a1", "label": "positive", "score": -0.8, "confidence": 0.9}

        with tempfile.TemporaryDirectory() as tmp:
            cache = JsonDiskCache(Path(tmp))
            openai = OpenAISentimentConfig(api_key="", model="test-model")

            with patch.object(cache, "get", return_value=cached), patch(
                "stock_sentiment.sentiment.analyze_articles_with_openai"
            ) as mocked:
                summary = analyze_with_cache(
                    ticker="TSLA",
                    query="TSLA",
                    articles=articles,
                    cache=cache,
                    cache_ttl_seconds=3600,
                    openai=openai,
                    include_reasons=False,
                )

        self.assertEqual(mocked.call_count, 0)
        self.assertAlmostEqual(summary.results[0].score, 0.8, places=6)
