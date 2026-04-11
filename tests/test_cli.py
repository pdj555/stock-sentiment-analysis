from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from stock_sentiment import cli
from stock_sentiment.errors import ConfigurationError, RemoteApiError
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


class TestCli(unittest.TestCase):
    def test_cli_json_omits_reasons_by_default(self) -> None:
        out = io.StringIO()
        err = io.StringIO()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=False), patch(
            "stock_sentiment.cli.load_dotenv"
        ), patch("stock_sentiment.cli.fetch_google_news_rss", return_value=[_fake_article()]), patch(
            "stock_sentiment.cli.analyze_with_cache", return_value=_fake_summary(include_reason=True)
        ):
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(["analyze", "tsla", "--format", "json", "--no-cache"])

        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["source"], "google-rss")
        self.assertEqual(payload["lookback_days"], 3)
        self.assertNotIn("reason", payload["results"][0])

    def test_cli_json_includes_reasons_when_requested(self) -> None:
        out = io.StringIO()
        err = io.StringIO()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=False), patch(
            "stock_sentiment.cli.load_dotenv"
        ), patch("stock_sentiment.cli.fetch_google_news_rss", return_value=[_fake_article()]), patch(
            "stock_sentiment.cli.analyze_with_cache", return_value=_fake_summary(include_reason=True)
        ):
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(["analyze", "tsla", "--format", "json", "--include-reasons", "--no-cache"])

        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["results"][0]["reason"], "reason")

    def test_cli_auto_falls_back_to_google_rss_on_newsapi_error(self) -> None:
        out = io.StringIO()
        err = io.StringIO()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "x", "NEWSAPI_KEY": "y"}, clear=False), patch(
            "stock_sentiment.cli.load_dotenv"
        ), patch("stock_sentiment.cli.fetch_everything", side_effect=RemoteApiError("nope")), patch(
            "stock_sentiment.cli.fetch_google_news_rss", return_value=[_fake_article()]
        ), patch("stock_sentiment.cli.analyze_with_cache", return_value=_fake_summary(include_reason=False)):
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(["analyze", "TSLA", "--format", "json", "--no-cache"])

        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["source"], "google-rss")
        self.assertIn("trying google news rss instead", err.getvalue().lower())

    def test_cli_allows_cache_only_run_without_openai_key(self) -> None:
        out = io.StringIO()
        err = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False), patch(
                "stock_sentiment.cli.load_dotenv"
            ), patch("stock_sentiment.cli.fetch_google_news_rss", return_value=[_fake_article()]), patch(
                "stock_sentiment.cli.analyze_with_cache", return_value=_fake_summary(include_reason=False)
            ):
                with redirect_stdout(out), redirect_stderr(err):
                    code = cli.main(
                        [
                            "analyze",
                            "TSLA",
                            "--format",
                            "json",
                            "--cache-dir",
                            str(Path(tmp)),
                        ]
                    )

        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["ticker"], "TSLA")

    def test_cli_env_file_sets_parser_backed_defaults(self) -> None:
        out = io.StringIO()
        err = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "custom.env"
            env_path.write_text(
                "OPENAI_API_KEY=x\nOPENAI_MODEL=from-env-file\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True), patch(
                "stock_sentiment.cli.fetch_google_news_rss", return_value=[_fake_article()]
            ), patch(
                "stock_sentiment.cli.analyze_with_cache",
                return_value=_fake_summary(include_reason=False),
            ) as mock_analyze:
                with redirect_stdout(out), redirect_stderr(err):
                    code = cli.main(
                        [
                            "analyze",
                            "TSLA",
                            "--env-file",
                            str(env_path),
                            "--no-cache",
                        ]
                    )

        self.assertEqual(code, 0)
        self.assertEqual(mock_analyze.call_args.kwargs["openai"].model, "from-env-file")

    def test_cli_rejects_missing_explicit_env_file(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, r"Env file not found:"):
            cli.main(["analyze", "TSLA", "--env-file", "does-not-exist.env"])

    def test_cli_google_rss_error_includes_next_step(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch(
            "stock_sentiment.cli.fetch_google_news_rss",
            side_effect=RemoteApiError("certificate verify failed"),
        ):
            with self.assertRaises(RemoteApiError) as ctx:
                cli.main(["analyze", "TSLA"])

        message = str(ctx.exception)
        self.assertIn("Google News RSS request failed.", message)
        self.assertIn("Set NEWSAPI_KEY to let auto prefer NewsAPI.", message)
        self.assertIn("certificate verify failed", message)

    def test_cli_prints_cache_warning_when_cache_read_fails(self) -> None:
        out = io.StringIO()
        err = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=False), patch(
                "stock_sentiment.cli.load_dotenv"
            ), patch(
                "stock_sentiment.cli.fetch_google_news_rss",
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
                with redirect_stdout(out), redirect_stderr(err):
                    code = cli.main(
                        [
                            "analyze",
                            "TSLA",
                            "--format",
                            "json",
                            "--cache-dir",
                            str(Path(tmp)),
                        ]
                    )

        self.assertEqual(code, 0)
        self.assertIn("Cache unavailable", err.getvalue())
        self.assertIn("OpenAI calls may repeat", err.getvalue())
