from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from stock_sentiment.sentiment import summarize_sentiment
from stock_sentiment.types import ArticleSentiment, NewsArticle


FIXED_NOW = datetime(2025, 1, 10, 12, 0, tzinfo=timezone.utc)


def _article(article_id: str, *, age_hours: float) -> NewsArticle:
    return NewsArticle(
        article_id=article_id,
        title=f"Article {article_id}",
        description="Fixture article",
        url=f"https://example.com/{article_id}",
        source="Example",
        published_at=FIXED_NOW - timedelta(hours=age_hours),
    )


class TestSentimentEval(unittest.TestCase):
    def test_summary_regression_cases(self) -> None:
        cases = [
            {
                "name": "bullish cluster produces buy",
                "results": [
                    ArticleSentiment("a1", "positive", 0.9, 0.9),
                    ArticleSentiment("a2", "positive", 0.7, 0.8),
                    ArticleSentiment("a3", "positive", 0.4, 0.7),
                ],
                "articles": {
                    "a1": _article("a1", age_hours=2),
                    "a2": _article("a2", age_hours=6),
                    "a3": _article("a3", age_hours=10),
                },
                "expected_label": "positive",
                "expected_signal": "buy",
                "score_range": (0.68, 0.73),
                "confidence_range": (0.80, 0.82),
            },
            {
                "name": "bearish cluster produces sell",
                "results": [
                    ArticleSentiment("a1", "negative", -0.8, 0.9),
                    ArticleSentiment("a2", "negative", -0.5, 0.8),
                    ArticleSentiment("a3", "negative", -0.3, 0.7),
                ],
                "articles": {
                    "a1": _article("a1", age_hours=1),
                    "a2": _article("a2", age_hours=5),
                    "a3": _article("a3", age_hours=10),
                },
                "expected_label": "negative",
                "expected_signal": "sell",
                "score_range": (-0.60, -0.55),
                "confidence_range": (0.80, 0.82),
            },
            {
                "name": "balanced mixed coverage stays neutral",
                "results": [
                    ArticleSentiment("a1", "positive", 0.8, 0.8),
                    ArticleSentiment("a2", "negative", -0.8, 0.8),
                ],
                "articles": {
                    "a1": _article("a1", age_hours=3),
                    "a2": _article("a2", age_hours=3),
                },
                "expected_label": "neutral",
                "expected_signal": "hold",
                "score_range": (-0.01, 0.01),
                "confidence_range": (0.79, 0.81),
            },
            {
                "name": "low confidence positive news stays hold",
                "results": [
                    ArticleSentiment("a1", "positive", 0.8, 0.2),
                    ArticleSentiment("a2", "positive", 0.6, 0.2),
                ],
                "articles": {
                    "a1": _article("a1", age_hours=1),
                    "a2": _article("a2", age_hours=5),
                },
                "expected_label": "positive",
                "expected_signal": "hold",
                "score_range": (0.68, 0.73),
                "confidence_range": (0.19, 0.21),
            },
            {
                "name": "recent news outweighs stale counter-signal",
                "results": [
                    ArticleSentiment("a1", "positive", 0.9, 0.9),
                    ArticleSentiment("a2", "negative", -0.9, 0.9),
                ],
                "articles": {
                    "a1": _article("a1", age_hours=2),
                    "a2": _article("a2", age_hours=72),
                },
                "expected_label": "positive",
                "expected_signal": "buy",
                "score_range": (0.68, 0.70),
                "confidence_range": (0.89, 0.91),
            },
        ]

        with patch("stock_sentiment.sentiment._utcnow", return_value=FIXED_NOW):
            for case in cases:
                with self.subTest(case=case["name"]):
                    summary = summarize_sentiment(
                        ticker="TSLA",
                        query="TSLA",
                        results=case["results"],
                        article_by_id=case["articles"],
                        half_life_hours=24.0,
                    )

                    self.assertEqual(summary.label, case["expected_label"])
                    self.assertEqual(summary.signal, case["expected_signal"])
                    self.assertGreaterEqual(summary.score, case["score_range"][0])
                    self.assertLessEqual(summary.score, case["score_range"][1])
                    self.assertGreaterEqual(
                        summary.confidence,
                        case["confidence_range"][0],
                    )
                    self.assertLessEqual(
                        summary.confidence,
                        case["confidence_range"][1],
                    )
