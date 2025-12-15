from __future__ import annotations

import unittest
from datetime import timezone
from unittest.mock import patch

from stock_sentiment.newsapi import fetch_everything


class TestNewsApi(unittest.TestCase):
    def test_fetch_everything_sends_key_in_header_not_url(self) -> None:
        with patch("stock_sentiment.newsapi.http_request_json", return_value={"articles": []}) as mocked:
            fetch_everything(api_key="SECRET", query="TSLA")

        self.assertEqual(mocked.call_count, 1)
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["headers"]["x-api-key"], "SECRET")
        self.assertNotIn("SECRET", kwargs["url"])
        self.assertNotIn("apiKey=", kwargs["url"])

    def test_fetch_everything_normalizes_naive_timestamps_to_utc(self) -> None:
        payload = {
            "articles": [
                {
                    "title": "t",
                    "description": "d",
                    "url": "https://example.com/a",
                    "source": {"name": "Example"},
                    "publishedAt": "2024-01-01T12:00:00",
                }
            ]
        }

        with patch("stock_sentiment.newsapi.http_request_json", return_value=payload):
            articles = fetch_everything(api_key="SECRET", query="TSLA")

        self.assertEqual(len(articles), 1)
        self.assertIsNotNone(articles[0].published_at)
        self.assertIs(articles[0].published_at.tzinfo, timezone.utc)

