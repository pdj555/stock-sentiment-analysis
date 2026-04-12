from __future__ import annotations

from datetime import datetime, timezone
from wsgiref.simple_server import WSGIRequestHandler, make_server

from stock_sentiment.runtime import AnalysisRunResult
from stock_sentiment.types import ArticleSentiment, NewsArticle, SentimentSummary
from stock_sentiment.ui import create_app


def _fake_result(ticker: str) -> AnalysisRunResult:
    normalized_ticker = str(ticker or "").strip().upper() or "TSLA"
    article = NewsArticle(
        article_id="a1",
        title=f"Example article for {normalized_ticker}",
        description="A short description",
        url="https://example.com/article",
        source="Example",
        published_at=datetime(2025, 1, 1, 15, 30, tzinfo=timezone.utc),
    )
    summary = SentimentSummary(
        ticker=normalized_ticker,
        query=normalized_ticker,
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
    )
    return AnalysisRunResult(
        summary=summary,
        articles=[article],
        source="google-rss",
        lookback_days=3,
        article_cap=18,
    )


class _QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return None


def main() -> int:
    app = create_app(_fake_result)
    with make_server("127.0.0.1", 0, app, handler_class=_QuietRequestHandler) as server:
        print(f"http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
