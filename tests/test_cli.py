from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from stock_sentiment import cli
from stock_sentiment.errors import ConfigurationError
from stock_sentiment.runtime import AnalysisRunResult
from stock_sentiment.types import (
    ArticleSentiment,
    EvidenceDriver,
    EvidenceProfile,
    NewsArticle,
    SentimentSummary,
)


def _fake_article(article_id: str = "a1") -> NewsArticle:
    return NewsArticle(
        article_id=article_id,
        title="t",
        description="d",
        url="https://example.com",
        source="Example",
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _fake_summary(
    *,
    include_reason: bool,
    classification_warnings: tuple[str, ...] = (),
) -> SentimentSummary:
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
        evidence=EvidenceProfile(
            grade="limited",
            coverage=0.5,
            agreement=0.75,
            classified_articles=1,
            total_articles=2,
            drivers=(
                EvidenceDriver(
                    article_id="a1",
                    title="t",
                    url="https://example.com",
                    source="Example",
                    published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    direction="positive",
                    impact=0.4,
                    confidence=0.5,
                    reason="reason" if include_reason else None,
                ),
            ),
        ),
        classification_degraded=bool(classification_warnings),
        classification_warnings=classification_warnings,
    )


def _fake_result(
    *,
    include_reason: bool,
    source: str = "google-rss",
    classification_warnings: tuple[str, ...] = (),
) -> AnalysisRunResult:
    return AnalysisRunResult(
        summary=_fake_summary(
            include_reason=include_reason,
            classification_warnings=classification_warnings,
        ),
        articles=[_fake_article()],
        source=source,
        lookback_days=3,
        article_cap=25,
    )


class TestCli(unittest.TestCase):
    def test_format_text_reads_like_user_facing_summary(self) -> None:
        rendered = cli._format_text(
            _fake_summary(include_reason=False),
            source_label="Google News RSS",
            lookback_days=3,
            article_cap=25,
        )

        self.assertIn("Google News RSS", rendered)
        self.assertIn("3-day lookback", rendered)
        self.assertIn("25-article cap", rendered)
        self.assertIn("signal no edge", rendered)
        self.assertIn("evidence limited, coverage 50%, agreement 75%", rendered)
        self.assertNotIn("lookback_days=", rendered)

    def test_format_text_renders_human_signal_copy(self) -> None:
        summary = _fake_summary(include_reason=False)

        bullish = cli._format_text(
            replace(summary, signal="buy"),
            source_label="Google News RSS",
            lookback_days=3,
            article_cap=25,
        )
        bearish = cli._format_text(
            replace(summary, signal="sell"),
            source_label="Google News RSS",
            lookback_days=3,
            article_cap=25,
        )

        self.assertIn("signal bullish", bullish)
        self.assertIn("signal bearish", bearish)

    def test_format_text_surfaces_classification_warnings(self) -> None:
        rendered = cli._format_text(
            _fake_summary(
                include_reason=False,
                classification_warnings=(
                    "OpenAI omitted classifications for 1 article; they were marked neutral with zero confidence.",
                ),
            ),
            source_label="Google News RSS",
            lookback_days=3,
            article_cap=25,
        )

        self.assertIn("Warning:", rendered)
        self.assertIn("OpenAI omitted classifications for 1 article", rendered)

    def test_module_entrypoint_help_for_analyze_command(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "stock_sentiment", "analyze", "TSLA", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Analyze recent news sentiment for a stock ticker.", result.stdout)
        self.assertIn("ticker", result.stdout)
        self.assertIn(
            "Search phrase used to find articles; defaults to",
            result.stdout,
        )
        self.assertIn("--env-file FILE", result.stdout)
        self.assertNotIn("--dotenv", result.stdout)

    def test_module_entrypoint_help_for_ui_command(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-m", "stock_sentiment", "ui", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Open a local web UI for one-ticker sentiment checks.", result.stdout)
        self.assertIn("OPENAI_API_KEY", result.stdout)
        self.assertIn("--port", result.stdout)
        self.assertIn("--env-file FILE", result.stdout)

    def test_cli_ui_starts_server(self) -> None:
        with patch("stock_sentiment.cli.load_dotenv"), patch(
            "stock_sentiment.ui.run_ui_server"
        ) as mock_run_ui_server:
            code = cli.main(["ui", "--host", "0.0.0.0", "--port", "9123"])

        self.assertEqual(code, 0)
        mock_run_ui_server.assert_called_once_with(host="0.0.0.0", port=9123)

    def test_cli_json_omits_reasons_by_default(self) -> None:
        out = io.StringIO()
        err = io.StringIO()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=False), patch(
            "stock_sentiment.cli.load_dotenv"
        ), patch(
            "stock_sentiment.cli.run_analysis",
            return_value=_fake_result(include_reason=True),
        ) as mock_run_analysis:
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(["analyze", "tsla", "--format", "json", "--no-cache"])

        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["source"], "google-rss")
        self.assertEqual(payload["source_label"], "Google News RSS")
        self.assertEqual(payload["lookback_days"], 3)
        self.assertEqual(payload["article_cap"], 25)
        self.assertFalse(payload["classification_degraded"])
        self.assertEqual(payload["classification_warnings"], [])
        self.assertEqual(payload["evidence"]["grade"], "limited")
        self.assertEqual(payload["evidence"]["coverage"], 0.5)
        self.assertEqual(payload["evidence"]["agreement"], 0.75)
        self.assertEqual(payload["evidence"]["classified_articles"], 1)
        self.assertEqual(payload["evidence"]["total_articles"], 2)
        self.assertEqual(payload["evidence"]["drivers"][0]["article_id"], "a1")
        self.assertTrue(payload["results"][0]["classified"])
        self.assertNotIn("reason", payload["results"][0])
        self.assertFalse(mock_run_analysis.call_args.args[0].include_reasons)

    def test_cli_json_includes_reasons_when_requested(self) -> None:
        out = io.StringIO()
        err = io.StringIO()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=False), patch(
            "stock_sentiment.cli.load_dotenv"
        ), patch(
            "stock_sentiment.cli.run_analysis",
            return_value=_fake_result(include_reason=True),
        ) as mock_run_analysis:
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(["analyze", "tsla", "--format", "json", "--include-reasons", "--no-cache"])

        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["results"][0]["reason"], "reason")
        self.assertTrue(mock_run_analysis.call_args.args[0].include_reasons)

    def test_cli_rejects_include_reasons_without_verbose_or_json(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=False), patch(
            "stock_sentiment.cli.load_dotenv"
        ):
            with self.assertRaisesRegex(
                ConfigurationError,
                r"--include-reasons requires --verbose or --format json\.",
            ):
                cli.main(["analyze", "TSLA", "--include-reasons", "--no-cache"])

    def test_cli_rejects_include_articles_without_json(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "x"}, clear=False), patch(
            "stock_sentiment.cli.load_dotenv"
        ):
            with self.assertRaisesRegex(
                ConfigurationError,
                r"--include-articles requires --format json\.",
            ):
                cli.main(["analyze", "TSLA", "--include-articles", "--no-cache"])

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
                "stock_sentiment.cli.run_analysis",
                return_value=_fake_result(include_reason=False),
            ) as mock_run_analysis:
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
        self.assertEqual(mock_run_analysis.call_args.args[0].openai_model, "from-env-file")

    def test_cli_dotenv_alias_still_sets_parser_backed_defaults(self) -> None:
        out = io.StringIO()
        err = io.StringIO()

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "legacy.env"
            env_path.write_text(
                "OPENAI_API_KEY=x\nOPENAI_MODEL=from-legacy-alias\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True), patch(
                "stock_sentiment.cli.run_analysis",
                return_value=_fake_result(include_reason=False),
            ) as mock_run_analysis:
                with redirect_stdout(out), redirect_stderr(err):
                    code = cli.main(
                        [
                            "analyze",
                            "TSLA",
                            "--dotenv",
                            str(env_path),
                            "--no-cache",
                        ]
                    )

        self.assertEqual(code, 0)
        self.assertEqual(
            mock_run_analysis.call_args.args[0].openai_model,
            "from-legacy-alias",
        )

    def test_cli_rejects_missing_explicit_env_file(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, r"Env file not found:"):
            cli.main(["analyze", "TSLA", "--env-file", "does-not-exist.env"])
