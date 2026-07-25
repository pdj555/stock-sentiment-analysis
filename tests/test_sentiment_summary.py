from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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
        self.assertEqual(summary.evidence.grade, "limited")
        self.assertEqual(summary.signal, "hold")
        self.assertEqual(summary.evidence.classified_articles, 2)

    def test_strong_aligned_evidence_emits_buy(self) -> None:
        now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
        articles = {
            f"a{index}": NewsArticle(
                article_id=f"a{index}",
                title=f"Headline {index}",
                description=f"Description {index}",
                url=f"https://example.com/{index}",
                source="Example",
                published_at=now - timedelta(minutes=index),
            )
            for index in range(1, 6)
        }
        results = [
            ArticleSentiment(
                article_id=article_id,
                label="positive",
                score=0.8,
                confidence=0.8,
                reason="Positive catalyst",
            )
            for article_id in articles
        ]

        with patch("stock_sentiment.sentiment._utcnow", return_value=now):
            strong = summarize_sentiment(
                ticker="XYZ",
                query="XYZ",
                results=results,
                article_by_id=articles,
            )

        self.assertEqual(strong.evidence.grade, "strong")
        self.assertEqual(strong.signal, "buy")
        self.assertAlmostEqual(strong.evidence.agreement, 1.0)

    def test_missing_rows_reduce_coverage_and_analyzed_count(self) -> None:
        now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
        articles = {
            f"a{index}": NewsArticle(
                article_id=f"a{index}",
                title=f"Headline {index}",
                description=f"Description {index}",
                url=f"https://example.com/{index}",
                source="Example",
                published_at=now - timedelta(minutes=index),
            )
            for index in range(1, 6)
        }
        results = [
            ArticleSentiment(
                article_id=article_id,
                label="positive" if index <= 3 else "neutral",
                score=0.8 if index <= 3 else 0.0,
                confidence=0.8 if index <= 3 else 0.0,
                reason="Positive catalyst" if index <= 3 else "No classification returned",
                classified=index <= 3,
            )
            for index, article_id in enumerate(articles, start=1)
        ]

        with patch("stock_sentiment.sentiment._utcnow", return_value=now):
            partial = summarize_sentiment(
                ticker="XYZ",
                query="XYZ",
                results=results,
                article_by_id=articles,
            )

        self.assertEqual(partial.evidence.classified_articles, 3)
        self.assertAlmostEqual(partial.evidence.coverage, 0.6)
        self.assertEqual(partial.articles_analyzed, 3)

    def test_drivers_retain_strongest_counter_direction(self) -> None:
        now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
        articles = {
            f"a{index}": NewsArticle(
                article_id=f"a{index}",
                title=f"Headline {index}",
                description=f"Description {index}",
                url=f"https://example.com/{index}",
                source="Example",
                published_at=now - timedelta(minutes=index),
            )
            for index in range(1, 5)
        }
        scores = [0.9, 0.7, 0.4, -0.85]
        results = [
            ArticleSentiment(
                article_id=article_id,
                label="positive" if score > 0 else "negative",
                score=score,
                confidence=0.8,
                reason="Positive catalyst" if score > 0 else "Material counter-signal",
            )
            for article_id, score in zip(articles, scores)
        ]

        with patch("stock_sentiment.sentiment._utcnow", return_value=now):
            mixed = summarize_sentiment(
                ticker="XYZ",
                query="XYZ",
                results=results,
                article_by_id=articles,
            )

        self.assertEqual(
            {driver.direction for driver in mixed.evidence.drivers},
            {"positive", "negative"},
        )
        self.assertEqual(len(mixed.evidence.drivers), 3)
        self.assertEqual(mixed.evidence.drivers[0].article_id, "a1")
