from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from threading import Thread
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server
from unittest.mock import patch

from app import app as deployed_app
from stock_sentiment.errors import ConfigurationError
from stock_sentiment.runtime import AnalysisRunResult
from stock_sentiment.types import ArticleSentiment, NewsArticle, SentimentSummary
from stock_sentiment.ui import (
    UI_HTML,
    _build_response_payload,
    _display_source_name,
    create_app,
)


def _fake_result(
    *,
    classification_warnings: tuple[str, ...] = (),
) -> AnalysisRunResult:
    article = NewsArticle(
        article_id="a1",
        title="Example article",
        description="A short description",
        url="https://example.com/article",
        source="Example",
        published_at=datetime(2025, 1, 1, 15, 30, tzinfo=timezone.utc),
    )
    summary = SentimentSummary(
        ticker="TSLA",
        query="TSLA",
        as_of=datetime(2025, 1, 1, 16, 0, tzinfo=timezone.utc),
        score=0.42,
        label="positive",
        confidence=0.81,
        signal="buy",
        articles_analyzed=1,
        results=[
            ArticleSentiment(
                article_id="a1",
                label="positive",
                score=0.42,
                confidence=0.81,
                reason="Demand outlook improved.",
            )
        ],
        classification_degraded=bool(classification_warnings),
        classification_warnings=classification_warnings,
    )
    return AnalysisRunResult(
        summary=summary,
        articles=[article],
        source="google-rss",
        lookback_days=3,
        article_cap=18,
    )


def _run_app(
    app,
    *,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[str, dict[str, str], dict[str, object]]:
    raw_body = b""
    if payload is not None:
        raw_body = json.dumps(payload).encode("utf-8")

    status_holder: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        status_holder["status"] = status
        status_holder["headers"] = headers

    body = b"".join(
        app(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "CONTENT_LENGTH": str(len(raw_body)),
                "wsgi.input": io.BytesIO(raw_body),
            },
            start_response,
        )
    )

    content_type = dict(status_holder["headers"]).get("Content-Type", "")
    parsed_body: dict[str, object]
    if content_type.startswith("application/json"):
        parsed_body = json.loads(body.decode("utf-8"))
    else:
        parsed_body = {"raw": body.decode("utf-8")}

    return (
        str(status_holder["status"]),
        dict(status_holder["headers"]),
        parsed_body,
    )


def _serve_http(app):
    server = make_server("127.0.0.1", 0, app, handler_class=_QuietRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


class _QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return None


class TestUi(unittest.TestCase):
    def test_ui_html_contains_primary_controls(self) -> None:
        self.assertIn("Recent news in one read.", UI_HTML)
        self.assertIn('id="ticker"', UI_HTML)
        self.assertIn("/api/analyze", UI_HTML)

    def test_build_response_payload_merges_article_sentiment(self) -> None:
        payload = _build_response_payload(_fake_result())

        self.assertEqual(payload["summary"]["ticker"], "TSLA")
        self.assertEqual(payload["summary"]["signal"], "buy")
        self.assertEqual(payload["summary"]["source"], "google-rss")
        self.assertEqual(payload["summary"]["source_label"], "Google News RSS")
        self.assertEqual(payload["summary"]["article_cap"], 18)
        self.assertFalse(payload["summary"]["classification_degraded"])
        self.assertEqual(payload["summary"]["classification_warnings"], [])
        self.assertEqual(payload["articles"][0]["reason"], "Demand outlook improved.")
        self.assertEqual(payload["articles"][0]["label"], "positive")

    def test_build_response_payload_includes_classification_warning_state(self) -> None:
        payload = _build_response_payload(
            _fake_result(
                classification_warnings=(
                    "OpenAI omitted classifications for 1 article; they were marked neutral with zero confidence.",
                )
            )
        )

        self.assertTrue(payload["summary"]["classification_degraded"])
        self.assertEqual(
            payload["summary"]["classification_warnings"],
            [
                "OpenAI omitted classifications for 1 article; they were marked neutral with zero confidence."
            ],
        )

    def test_display_source_name_hides_internal_slugs(self) -> None:
        self.assertEqual(_display_source_name("newsapi"), "NewsAPI")
        self.assertEqual(_display_source_name("google-rss"), "Google News RSS")

    def test_wsgi_app_serves_html_shell(self) -> None:
        app = create_app(lambda ticker: _fake_result())

        status, headers, payload = _run_app(app, method="GET", path="/")

        self.assertEqual(status, "200 OK")
        self.assertTrue(headers["Content-Type"].startswith("text/html"))
        self.assertIn("Stock Sentiment", payload["raw"])

    def test_wsgi_app_returns_analysis_payload(self) -> None:
        app = create_app(lambda ticker: _fake_result())

        status, headers, payload = _run_app(
            app,
            method="POST",
            path="/api/analyze",
            payload={"ticker": "TSLA"},
        )

        self.assertEqual(status, "200 OK")
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        self.assertEqual(payload["summary"]["ticker"], "TSLA")
        self.assertEqual(len(payload["articles"]), 1)

    def test_wsgi_app_surfaces_validation_errors(self) -> None:
        app = create_app(
            lambda ticker: (_ for _ in ()).throw(
                ConfigurationError("Ticker cannot be empty.")
            )
        )

        status, _, payload = _run_app(
            app,
            method="POST",
            path="/api/analyze",
            payload={"ticker": ""},
        )

        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(payload["error"]["message"], "Ticker cannot be empty.")

    def test_wsgi_app_rejects_non_string_ticker(self) -> None:
        app = create_app(lambda ticker: _fake_result())

        status, _, payload = _run_app(
            app,
            method="POST",
            path="/api/analyze",
            payload={"ticker": ["TSLA"]},
        )

        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(
            payload["error"]["message"],
            'Ticker must be a string like "TSLA".',
        )

    def test_wsgi_app_rejects_invalid_json_with_example(self) -> None:
        app = create_app(lambda ticker: _fake_result())
        raw_body = b"{not-json"
        status_holder: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            status_holder["status"] = status
            status_holder["headers"] = headers

        body = b"".join(
            app(
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": "/api/analyze",
                    "CONTENT_LENGTH": str(len(raw_body)),
                    "wsgi.input": io.BytesIO(raw_body),
                },
                start_response,
            )
        )
        payload = json.loads(body.decode("utf-8"))

        self.assertEqual(status_holder["status"], "400 Bad Request")
        self.assertEqual(
            payload["error"]["message"],
            'Request body must be valid JSON like {"ticker":"TSLA"}.',
        )

    def test_wsgi_app_rejects_non_object_json_with_example(self) -> None:
        app = create_app(lambda ticker: _fake_result())
        raw_body = b"[]"
        status_holder: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            status_holder["status"] = status
            status_holder["headers"] = headers

        body = b"".join(
            app(
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": "/api/analyze",
                    "CONTENT_LENGTH": str(len(raw_body)),
                    "wsgi.input": io.BytesIO(raw_body),
                },
                start_response,
            )
        )
        payload = json.loads(body.decode("utf-8"))

        self.assertEqual(status_holder["status"], "400 Bad Request")
        self.assertEqual(
            payload["error"]["message"],
            'Request body must be a JSON object like {"ticker":"TSLA"}.',
        )

    def test_wsgi_app_surfaces_unexpected_error_with_next_step(self) -> None:
        app = create_app(lambda ticker: (_ for _ in ()).throw(RuntimeError("boom")))

        with io.StringIO() as err, patch("sys.stderr", err):
            status, _, payload = _run_app(
                app,
                method="POST",
                path="/api/analyze",
                payload={"ticker": "TSLA"},
            )
            logged = err.getvalue()

        self.assertEqual(status, "500 Internal Server Error")
        self.assertEqual(
            payload["error"]["message"],
            "Analysis failed unexpectedly. Try again in a moment or check the server logs.",
        )
        self.assertIn("RuntimeError: boom", logged)

    def test_wsgi_app_404_includes_route_guidance(self) -> None:
        app = create_app(lambda ticker: _fake_result())

        status, _, payload = _run_app(app, method="GET", path="/missing")

        self.assertEqual(status, "404 Not Found")
        self.assertEqual(
            payload["error"]["message"],
            "That page was not found. Open / in a browser or POST JSON to /api/analyze.",
        )

    def test_http_server_serves_health_and_analysis(self) -> None:
        app = create_app(lambda ticker: _fake_result())
        server, thread, base_url = _serve_http(app)

        try:
            with urlopen(f"{base_url}/health", timeout=2) as response:
                self.assertEqual(json.load(response), {"ok": True})

            request = Request(
                f"{base_url}/api/analyze",
                data=json.dumps({"ticker": "TSLA"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                payload = json.load(response)

            self.assertEqual(payload["summary"]["ticker"], "TSLA")
            self.assertEqual(payload["summary"]["source"], "google-rss")
            self.assertEqual(payload["summary"]["source_label"], "Google News RSS")
            self.assertEqual(payload["summary"]["article_cap"], 18)
            self.assertFalse(payload["summary"]["classification_degraded"])
            self.assertEqual(payload["summary"]["classification_warnings"], [])
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def test_root_app_entrypoint_serves_health(self) -> None:
        status, headers, payload = _run_app(deployed_app, method="GET", path="/health")

        self.assertEqual(status, "200 OK")
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        self.assertEqual(payload, {"ok": True})
