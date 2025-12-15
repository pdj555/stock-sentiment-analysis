from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from stock_sentiment.sentiment import summarize_sentiment
from stock_sentiment.types import ArticleSentiment, NewsArticle


class TestSentimentSummary(unittest.TestCase):
    def test_summary_score_and_label(self) -> None:
        now = datetime.now(timezone.utc)
        articles = {
            "a1": NewsArticle(
                article_id="a1",
                title="t",
                description="d",
                url=None,
                source=None,
                published_at=now,
            ),
            "a2": NewsArticle(
                article_id="a2",
                title="t2",
                description="d2",
                url=None,
                source=None,
                published_at=now - timedelta(days=3),
            ),
        }

        results = [
            ArticleSentiment(article_id="a1", label="positive", score=1.0, confidence=1.0),
            ArticleSentiment(article_id="a2", label="negative", score=-1.0, confidence=1.0),
        ]

        summary = summarize_sentiment(
            ticker="XYZ",
            query="XYZ",
            results=results,
            article_by_id=articles,
            half_life_hours=24.0,
        )

        self.assertIn(summary.label, {"positive", "negative", "neutral"})
        self.assertIn(summary.signal, {"buy", "sell", "hold"})
        self.assertGreaterEqual(summary.score, -1.0)
        self.assertLessEqual(summary.score, 1.0)
