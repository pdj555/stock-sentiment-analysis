from __future__ import annotations

import gzip
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch

from stock_sentiment.errors import RemoteApiError
from stock_sentiment.http import HttpResponse, http_request_bytes, http_request_json


class TestHttpContract(unittest.TestCase):
    def test_http_request_json_honors_retry_after_cap(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        retry_after = format_datetime(now + timedelta(seconds=120), usegmt=True)
        responses = [
            (HttpResponse(status=429, headers={"retry-after": retry_after}, body=b""), None),
            (HttpResponse(status=200, headers={}, body=b"{}"), None),
        ]

        with patch("stock_sentiment.http._request", side_effect=responses) as mock_request, patch(
            "stock_sentiment.http._utcnow",
            return_value=now,
        ), patch("stock_sentiment.http.random.random", return_value=0.0), patch(
            "stock_sentiment.http.time.sleep"
        ) as mock_sleep:
            payload = http_request_json(
                method="GET",
                url="https://example.com/data",
                max_retries=1,
                max_retry_after_seconds=45.0,
            )

        self.assertEqual(payload, {})
        self.assertEqual(mock_request.call_count, 2)
        mock_sleep.assert_called_once_with(45.0)

    def test_http_request_json_reports_tls_hint(self) -> None:
        error = urllib.error.URLError("certificate verify failed")
        with patch(
            "stock_sentiment.http._request",
            return_value=(HttpResponse(status=0, headers={}, body=b""), error),
        ):
            with self.assertRaises(RemoteApiError) as ctx:
                http_request_json(
                    method="GET",
                    url="https://example.com/data",
                    max_retries=0,
                )

        message = str(ctx.exception)
        self.assertIn("certificate verify failed", message)
        self.assertIn("Check your local TLS certificates or trust store.", message)

    def test_http_request_json_reports_retry_exhaustion_for_network_failures(self) -> None:
        error = urllib.error.URLError("network is unreachable")
        responses = [
            (HttpResponse(status=0, headers={}, body=b""), error),
            (HttpResponse(status=0, headers={}, body=b""), error),
        ]

        with patch("stock_sentiment.http._request", side_effect=responses), patch(
            "stock_sentiment.http.random.random",
            return_value=0.0,
        ), patch("stock_sentiment.http.time.sleep"):
            with self.assertRaises(RemoteApiError) as ctx:
                http_request_json(
                    method="GET",
                    url="https://example.com/data",
                    max_retries=1,
                )

        message = str(ctx.exception)
        self.assertIn("failed after retries", message)
        self.assertIn("Check your network connection and try again.", message)

    def test_http_request_json_decompresses_gzip_body(self) -> None:
        compressed = gzip.compress(b'{"ok": true}')
        with patch(
            "stock_sentiment.http._request",
            return_value=(
                HttpResponse(
                    status=200,
                    headers={"content-encoding": "gzip", "content-length": str(len(compressed))},
                    body=compressed,
                ),
                None,
            ),
        ):
            payload = http_request_json(
                method="GET",
                url="https://example.com/data",
                max_retries=0,
            )

        self.assertEqual(payload, {"ok": True})

    def test_http_request_bytes_retries_transient_5xx_and_decompresses(self) -> None:
        compressed = gzip.compress(b"hello")
        responses = [
            (HttpResponse(status=503, headers={}, body=b"temporary"), None),
            (
                HttpResponse(
                    status=200,
                    headers={"content-encoding": "gzip"},
                    body=compressed,
                ),
                None,
            ),
        ]

        with patch("stock_sentiment.http._request", side_effect=responses) as mock_request, patch(
            "stock_sentiment.http.random.random",
            return_value=0.0,
        ), patch("stock_sentiment.http.time.sleep") as mock_sleep:
            body = http_request_bytes(
                method="GET",
                url="https://example.com/raw",
                max_retries=1,
            )

        self.assertEqual(body, b"hello")
        self.assertEqual(mock_request.call_count, 2)
        mock_sleep.assert_called_once()

    def test_http_request_bytes_reports_provider_failure_hint(self) -> None:
        with patch(
            "stock_sentiment.http._request",
            return_value=(HttpResponse(status=503, headers={}, body=b"service down"), None),
        ):
            with self.assertRaises(RemoteApiError) as ctx:
                http_request_bytes(
                    method="GET",
                    url="https://example.com/raw",
                    max_retries=0,
                )

        self.assertIn("The provider is having trouble. Try again shortly.", str(ctx.exception))

    def test_http_request_bytes_reports_rate_limit_hint(self) -> None:
        with patch(
            "stock_sentiment.http._request",
            return_value=(
                HttpResponse(
                    status=429,
                    headers={},
                    body=b'{"message":"Too many requests"}',
                ),
                None,
            ),
        ):
            with self.assertRaises(RemoteApiError) as ctx:
                http_request_bytes(
                    method="GET",
                    url="https://example.com/raw",
                    max_retries=0,
                )

        self.assertIn("Wait a moment and try again.", str(ctx.exception))
