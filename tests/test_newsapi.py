from __future__ import annotations

import unittest
from datetime import timezone
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from stock_sentiment.newsapi import fetch_everything


def _newsapi_article(url: str, published_at: str = "2024-01-01T12:00:00Z") -> dict[str, object]:
    return {
        "title": f"title-{url.rsplit('/', 1)[-1]}",
        "description": "d",
        "url": url,
        "source": {"name": "Example"},
        "publishedAt": published_at,
    }


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

    def test_fetch_everything_paginates_until_limit(self) -> None:
        payloads = [
            {
                "articles": [
                    _newsapi_article("https://example.com/a1"),
                    _newsapi_article("https://example.com/a2"),
                ]
            },
            {"articles": [_newsapi_article("https://example.com/a3")]},
        ]
        seen_urls: list[str] = []

        def fake_http_request_json(**kwargs: object) -> dict[str, object]:
            seen_urls.append(str(kwargs["url"]))
            return payloads[len(seen_urls) - 1]

        with patch(
            "stock_sentiment.newsapi.http_request_json",
            side_effect=fake_http_request_json,
        ):
            articles = fetch_everything(
                api_key="SECRET",
                query="TSLA",
                page_size=2,
                limit=3,
            )

        self.assertEqual(len(articles), 3)
        self.assertEqual(
            [article.url for article in articles],
            [
                "https://example.com/a1",
                "https://example.com/a2",
                "https://example.com/a3",
            ],
        )
        queries = [parse_qs(urlsplit(url).query) for url in seen_urls]
        self.assertEqual(queries[0]["page"], ["1"])
        self.assertEqual(queries[0]["pageSize"], ["2"])
        self.assertEqual(queries[1]["page"], ["2"])
        self.assertEqual(queries[1]["pageSize"], ["1"])

    def test_fetch_everything_stops_after_short_page(self) -> None:
        payloads = [
            {
                "articles": [
                    _newsapi_article("https://example.com/a1"),
                    _newsapi_article("https://example.com/a2"),
                ]
            },
            {"articles": [_newsapi_article("https://example.com/a3")]},
        ]

        with patch(
            "stock_sentiment.newsapi.http_request_json",
            side_effect=payloads,
        ) as mocked:
            articles = fetch_everything(
                api_key="SECRET",
                query="TSLA",
                page_size=2,
                limit=5,
            )

        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(len(articles), 3)
