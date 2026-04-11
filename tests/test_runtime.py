from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from stock_sentiment.errors import ConfigurationError, RemoteApiError
from stock_sentiment.runtime import AnalysisRequest, run_analysis
from stock_sentiment.types import ArticleSentiment, NewsArticle, SentimentSummary


def _fake_article(article_id: str = "a1") -> NewsArticle:
    return NewsArticle(
        article_id=article_id,
        title="t",
        description="d",
        url="https://example.com",
        source="Example",
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _fake_summary(*, include_reason: bool) -> SentimentSummary:
    return SentimentSummary(
        ticker="TSLA",
        query="TSLA",
        as_of=datetime(2025, 1, 1, tzinfo=timezone.utc),
        score=0.1,
        label="neutral",
        confidence=0.5,
        signal="hold",
        articles_analyzed=1,
        results=[
            ArticleSentiment(
                article_id="a1",
                label="neutral",
                score=0.0,
                confidence=0.5,
                reason="reason" if include_reason else None,
            )
        ],
    )


class TestRuntime(unittest.TestCase):
    def test_run_analysis_auto_falls_back_to_google_rss_on_newsapi_error(self) -> None:
        warnings: list[str] = []

        with patch(
            "stock_sentiment.runtime.fetch_everything",
            side_effect=RemoteApiError("nope"),
        ), patch(
            "stock_sentiment.runtime.fetch_google_news_rss",
            return_value=[_fake_article()],
        ), patch(
            "stock_sentiment.runtime.analyze_with_cache",
            return_value=_fake_summary(include_reason=False),
        ):
            result = run_analysis(
                AnalysisRequest(
                    ticker="TSLA",
                    source="auto",
                    openai_api_key="x",
                    newsapi_key="y",
                    use_cache=False,
                ),
                warn=warnings.append,
            )

        self.assertEqual(result.source, "google-rss")
        self.assertTrue(
            any("Trying Google News RSS instead." in message for message in warnings)
        )

    def test_run_analysis_allows_cache_only_run_without_openai_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch(
            "stock_sentiment.runtime.fetch_google_news_rss",
            return_value=[_fake_article()],
        ), patch(
            "stock_sentiment.runtime.analyze_with_cache",
            return_value=_fake_summary(include_reason=False),
        ):
            result = run_analysis(
                AnalysisRequest(
                    ticker="TSLA",
                    openai_api_key="",
                    cache_dir=Path(tmp),
                )
            )

        self.assertEqual(result.summary.ticker, "TSLA")

    def test_run_analysis_google_rss_error_includes_next_step(self) -> None:
        with patch(
            "stock_sentiment.runtime.fetch_google_news_rss",
            side_effect=RemoteApiError("certificate verify failed"),
        ):
            with self.assertRaises(RemoteApiError) as ctx:
                run_analysis(
                    AnalysisRequest(
                        ticker="TSLA",
                        openai_api_key="x",
                        use_cache=False,
                    )
                )

        message = str(ctx.exception)
        self.assertIn("Google News RSS request failed.", message)
        self.assertIn("Set NEWSAPI_KEY to let auto prefer NewsAPI.", message)
        self.assertIn("certificate verify failed", message)

    def test_run_analysis_reports_cache_warning_when_cache_read_fails(self) -> None:
        warnings: list[str] = []

        with tempfile.TemporaryDirectory() as tmp, patch(
            "stock_sentiment.runtime.fetch_google_news_rss",
            return_value=[_fake_article()],
        ), patch(
            "pathlib.Path.read_text",
            side_effect=OSError("cache read failed"),
        ), patch(
            "stock_sentiment.sentiment.analyze_articles_with_openai",
            return_value=[
                ArticleSentiment(
                    article_id="a1",
                    label="neutral",
                    score=0.0,
                    confidence=0.5,
                )
            ],
        ):
            result = run_analysis(
                AnalysisRequest(
                    ticker="TSLA",
                    openai_api_key="x",
                    cache_dir=Path(tmp),
                ),
                warn=warnings.append,
            )

        self.assertEqual(result.summary.ticker, "TSLA")
        self.assertTrue(any("Cache unavailable" in message for message in warnings))
        self.assertTrue(any("OpenAI calls may repeat" in message for message in warnings))

    def test_run_analysis_rejects_invalid_openai_base_url(self) -> None:
        with self.assertRaisesRegex(
            ConfigurationError,
            r"OpenAI base URL must be an http\(s\) URL",
        ):
            run_analysis(
                AnalysisRequest(
                    ticker="TSLA",
                    openai_api_key="x",
                    openai_base_url="not-a-url",
                    use_cache=False,
                )
            )
