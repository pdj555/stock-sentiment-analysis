from __future__ import annotations

import unittest
from unittest.mock import patch

from stock_sentiment.errors import RemoteApiError
from stock_sentiment.http import HttpResponse, http_request_json


class TestHttp(unittest.TestCase):
    def test_http_request_json_redacts_secrets_in_error_urls(self) -> None:
        def fake_request(*, method: str, url: str, headers: dict[str, str], data: bytes | None, timeout_seconds: float):
            body = b'{"status":"error","code":"apiKeyInvalid","message":"Invalid API key"}'
            return HttpResponse(status=401, headers={}, body=body), None

        with patch("stock_sentiment.http._request", side_effect=fake_request):
            with self.assertRaises(RemoteApiError) as ctx:
                http_request_json(
                    method="GET",
                    url="https://newsapi.org/v2/everything?apiKey=SECRET&q=TSLA",
                    max_retries=0,
                )

        message = str(ctx.exception)
        self.assertNotIn("SECRET", message)
        self.assertIn("REDACTED", message)
        self.assertIn("Invalid API key", message)

    def test_http_request_json_redacts_secrets_on_json_parse_errors(self) -> None:
        def fake_request(*, method: str, url: str, headers: dict[str, str], data: bytes | None, timeout_seconds: float):
            return HttpResponse(status=200, headers={}, body=b"not json"), None

        with patch("stock_sentiment.http._request", side_effect=fake_request):
            with self.assertRaises(RemoteApiError) as ctx:
                http_request_json(
                    method="GET",
                    url="https://example.com/data?token=SECRET",
                    max_retries=0,
                )

        message = str(ctx.exception)
        self.assertNotIn("SECRET", message)
        self.assertIn("REDACTED", message)
        self.assertIn("invalid JSON", message)

    def test_http_request_json_errors_on_non_object_json(self) -> None:
        def fake_request(*, method: str, url: str, headers: dict[str, str], data: bytes | None, timeout_seconds: float):
            return HttpResponse(status=200, headers={}, body=b"[]"), None

        with patch("stock_sentiment.http._request", side_effect=fake_request):
            with self.assertRaises(RemoteApiError) as ctx:
                http_request_json(
                    method="GET",
                    url="https://example.com/data?token=SECRET",
                    max_retries=0,
                )

        message = str(ctx.exception)
        self.assertNotIn("SECRET", message)
        self.assertIn("REDACTED", message)
        self.assertIn("unexpected JSON type", message)
