from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from stock_sentiment.cache import JsonDiskCache
from stock_sentiment.errors import ParseError
from stock_sentiment.sentiment import (
    OpenAIClassificationBatch,
    OpenAISentimentConfig,
    analyze_articles_with_openai,
    analyze_with_cache,
)
from stock_sentiment.types import ArticleSentiment, NewsArticle


def _article(article_id: str) -> NewsArticle:
    return NewsArticle(
        article_id=article_id,
        title=f"Article {article_id}",
        description="Description",
        url=f"https://example.com/{article_id}",
        source="Example",
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


class TestSentimentOpenAIContract(unittest.TestCase):
    def test_analyze_articles_with_openai_flags_missing_classifications(self) -> None:
        response = {
            "output_text": json.dumps(
                {
                    "results": [
                        {
                            "article_id": "a1",
                            "label": "positive",
                            "score": 0.8,
                            "confidence": 0.9,
                            "reason": "Demand improved.",
                        }
                    ]
                }
            )
        }

        with patch(
            "stock_sentiment.sentiment.create_response",
            return_value=response,
        ) as mocked:
            batch = analyze_articles_with_openai(
                ticker="TSLA",
                articles=[_article("a1"), _article("a2")],
                openai=OpenAISentimentConfig(api_key="test"),
                include_reasons=True,
            )

        self.assertIn("text_format", mocked.call_args.kwargs)
        self.assertNotIn("response_format", mocked.call_args.kwargs)

        self.assertEqual(batch.missing_article_ids, ("a2",))
        self.assertEqual(batch.results[1].article_id, "a2")
        self.assertEqual(batch.results[1].label, "neutral")
        self.assertEqual(batch.results[1].confidence, 0.0)
        self.assertEqual(batch.results[1].reason, "No classification returned")

    def test_analyze_articles_with_openai_counts_invalid_duplicate_and_unexpected_rows(self) -> None:
        response = {
            "output_text": json.dumps(
                {
                    "results": [
                        {
                            "article_id": "a1",
                            "label": "positive",
                            "score": 0.8,
                            "confidence": 0.9,
                        },
                        {
                            "article_id": "a1",
                            "label": "negative",
                            "score": -0.4,
                            "confidence": 0.7,
                        },
                        {
                            "article_id": "a9",
                            "label": "positive",
                            "score": 0.5,
                            "confidence": 0.6,
                        },
                        {
                            "article_id": "",
                            "label": "neutral",
                            "score": 0.0,
                            "confidence": 0.5,
                        },
                        "bad-row",
                    ]
                }
            )
        }

        with patch("stock_sentiment.sentiment.create_response", return_value=response):
            batch = analyze_articles_with_openai(
                ticker="TSLA",
                articles=[_article("a1"), _article("a2")],
                openai=OpenAISentimentConfig(api_key="test"),
                include_reasons=False,
            )

        self.assertEqual(batch.duplicate_result_count, 1)
        self.assertEqual(batch.unexpected_result_count, 1)
        self.assertEqual(batch.invalid_row_count, 2)
        self.assertEqual(batch.missing_article_ids, ("a2",))

    def test_analyze_articles_with_openai_rejects_invalid_json(self) -> None:
        with patch(
            "stock_sentiment.sentiment.create_response",
            return_value={"output_text": "{not json"},
        ):
            with self.assertRaisesRegex(ParseError, r"OpenAI output was not valid JSON"):
                analyze_articles_with_openai(
                    ticker="TSLA",
                    articles=[_article("a1")],
                    openai=OpenAISentimentConfig(api_key="test"),
                    include_reasons=False,
                )

    def test_analyze_with_cache_marks_partial_openai_results_as_degraded(self) -> None:
        articles = [_article("a1"), _article("a2")]
        batch = OpenAIClassificationBatch(
            results=[
                ArticleSentiment(
                    article_id="a1",
                    label="positive",
                    score=0.8,
                    confidence=0.9,
                    reason="Demand improved.",
                ),
                ArticleSentiment(
                    article_id="a2",
                    label="neutral",
                    score=0.0,
                    confidence=0.0,
                    reason="No classification returned",
                ),
            ],
            missing_article_ids=("a2",),
        )

        with tempfile.TemporaryDirectory() as tmp:
            cache = JsonDiskCache(Path(tmp))
            with patch(
                "stock_sentiment.sentiment.analyze_articles_with_openai",
                return_value=batch,
            ), patch.object(cache, "set", wraps=cache.set) as mock_cache_set:
                summary = analyze_with_cache(
                    ticker="TSLA",
                    query="TSLA",
                    articles=articles,
                    cache=cache,
                    cache_ttl_seconds=3600,
                    openai=OpenAISentimentConfig(api_key="test", model="test-model"),
                    include_reasons=True,
                )

        self.assertTrue(summary.classification_degraded)
        self.assertEqual(
            summary.classification_warnings,
            (
                "OpenAI omitted classifications for 1 article; they were marked neutral with zero confidence.",
            ),
        )
        cached_article_ids = [call.args[1]["article_id"] for call in mock_cache_set.call_args_list]
        self.assertEqual(cached_article_ids, ["a1"])
