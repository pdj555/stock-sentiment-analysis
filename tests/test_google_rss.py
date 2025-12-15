from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from stock_sentiment.errors import ParseError
from stock_sentiment.google_rss import fetch_google_news_rss


class TestGoogleRss(unittest.TestCase):
    def test_fetch_google_news_rss_parses_items(self) -> None:
        rss = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Google News</title>
    <item>
      <title>TSLA rallies - Example News</title>
      <link>https://example.com/article1</link>
      <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
      <description><![CDATA[<b>TSLA</b> up on earnings]]></description>
      <source url="https://example.com">Example</source>
    </item>
  </channel>
</rss>
"""

        with patch("stock_sentiment.google_rss.http_request_bytes", return_value=rss):
            articles = fetch_google_news_rss(
                query="TSLA",
                from_datetime=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].url, "https://example.com/article1")
        self.assertIn("TSLA rallies", articles[0].title)
        self.assertIn("TSLA up on earnings", articles[0].description)

    def test_fetch_google_news_rss_filters_by_datetime(self) -> None:
        rss = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Old</title>
      <link>https://example.com/old</link>
      <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
      <description>old</description>
    </item>
  </channel>
</rss>
"""

        with patch("stock_sentiment.google_rss.http_request_bytes", return_value=rss):
            articles = fetch_google_news_rss(
                query="TSLA",
                from_datetime=datetime(2024, 2, 1, tzinfo=timezone.utc),
            )

        self.assertEqual(articles, [])

    def test_fetch_google_news_rss_raises_parse_error_on_invalid_xml(self) -> None:
        with patch("stock_sentiment.google_rss.http_request_bytes", return_value=b"<not xml"):
            with self.assertRaises(ParseError):
                fetch_google_news_rss(query="TSLA")
