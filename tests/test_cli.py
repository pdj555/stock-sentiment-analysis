from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from stock_sentiment import cli
from stock_sentiment.errors import ConfigurationError
from stock_sentiment.runtime import AnalysisRunResult
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


def _fake_result(*, include_reason: bool, source: str = "google-rss") -> AnalysisRunResult:
    return AnalysisRunResult(
        summary=_fake_summary(include_reason=include_reason),
        articles=[_fake_article()],
        source=source,
        lookback_days=3,
    )


class TestCli(unittest.TestCase):
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
        self.assertIn("--port", result.stdout)

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
        self.assertEqual(payload["lookback_days"], 3)
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

    def test_cli_rejects_missing_explicit_env_file(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, r"Env file not found:"):
            cli.main(["analyze", "TSLA", "--env-file", "does-not-exist.env"])
