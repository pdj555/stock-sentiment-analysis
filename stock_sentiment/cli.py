from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from stock_sentiment import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    __version__,
)
from stock_sentiment.cache import JsonDiskCache
from stock_sentiment.env import load_dotenv
from stock_sentiment.errors import (
    ConfigurationError,
    RemoteApiError,
    StockSentimentError,
)
from stock_sentiment.google_rss import fetch_google_news_rss
from stock_sentiment.newsapi import fetch_everything
from stock_sentiment.sentiment import OpenAISentimentConfig, analyze_with_cache
from stock_sentiment.types import SentimentSummary


def _default_cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "stock_sentiment"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "stock_sentiment"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "stock_sentiment"
    return Path.home() / ".cache" / "stock_sentiment"


def _format_text(summary: SentimentSummary, *, source: str, lookback_days: int) -> str:
    score = f"{summary.score:+.3f}"
    conf = f"{summary.confidence:.2f}"
    as_of = summary.as_of.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    return (
        f"{summary.ticker} sentiment {score} ({summary.label}, confidence {conf}) "
        f"signal={summary.signal} articles={summary.articles_analyzed} "
        f"source={source} window={lookback_days}d as_of={as_of}"
    )


def _argv_list(argv: list[str] | None) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)


def _resolve_env_file(argv: list[str]) -> tuple[Path, bool]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--env-file", "--dotenv", dest="env_file", type=Path)
    parsed, _ = parser.parse_known_args(argv)
    env_file = parsed.env_file or Path(".env")
    return env_file, parsed.env_file is not None


def _fetch_google_news_rss_with_guidance(
    *,
    query: str,
    from_datetime: datetime,
    source_requested: str,
    newsapi_key_present: bool,
):
    try:
        return fetch_google_news_rss(query=query, from_datetime=from_datetime)
    except RemoteApiError as e:
        lower = str(e).lower()
        parts: list[str] = []
        if any(
            token in lower
            for token in [
                "certificate verify failed",
                "timed out",
                "ssl",
                "failed (0)",
                "failed after retries",
                "network is unreachable",
                "connection reset",
                "connection refused",
            ]
        ):
            parts.append("Check your network connection or local TLS certificates.")
        if source_requested == "auto" and not newsapi_key_present:
            parts.append("Set NEWSAPI_KEY to let auto prefer NewsAPI.")
        guidance = f" {' '.join(parts)}" if parts else ""
        raise RemoteApiError(
            f"Google News RSS request failed.{guidance} Original error: {e}"
        ) from e


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stock-sentiment",
        description="Score recent stock news sentiment with OpenAI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  stock-sentiment analyze TSLA\n"
            "  stock-sentiment analyze TSLA --format json --include-reasons\n"
            "  stock-sentiment analyze TSLA --source google-rss --days 7\n"
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser(
        "analyze",
        help="Score recent news sentiment for a ticker",
        description="Analyze recent news sentiment for a stock ticker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Quick start:\n"
            "  export OPENAI_API_KEY=...\n"
            "  stock-sentiment analyze TSLA\n\n"
            "Notes:\n"
            "  --source auto prefers NewsAPI when NEWSAPI_KEY is set, otherwise Google News RSS.\n"
            "  --env-file PATH reads env vars from PATH instead of ./.env in the current working directory.\n"
        ),
    )
    analyze.add_argument("ticker", help="Stock ticker symbol (e.g., TSLA)")
    analyze.add_argument(
        "--query",
        help="Override the news search text (advanced; defaults to ticker)",
    )
    analyze.add_argument(
        "--days", type=int, default=3, help="Look back this many days (default: 3)"
    )
    tuning = analyze.add_argument_group("Scoring and sourcing")
    tuning.add_argument(
        "--max-articles",
        type=int,
        default=25,
        help="Analyze at most this many unique articles (default: 25)",
    )
    tuning.add_argument(
        "--half-life-hours",
        type=float,
        default=24.0,
        help="Downweight older articles after this many hours (default: 24)",
    )
    output = analyze.add_argument_group("Output")
    output.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Print a one-line summary or JSON",
    )
    output.add_argument(
        "--include-reasons",
        action="store_true",
        help="Include a short reason for each article in JSON output and verbose text output",
    )
    output.add_argument(
        "--include-articles",
        action="store_true",
        help="Embed article metadata in JSON output",
    )
    output.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-article details after the summary",
    )
    tuning.add_argument(
        "--source",
        choices=["auto", "newsapi", "google-rss"],
        default="auto",
        help="Choose the news source. 'auto' prefers NewsAPI, then falls back to Google News RSS.",
    )
    cache = analyze.add_argument_group("Caching")
    cache.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip the local OpenAI cache for this run",
    )
    cache.add_argument(
        "--cache-ttl-hours",
        type=float,
        default=24.0,
        help="Reuse cached article classifications for this many hours (default: 24)",
    )
    cache.add_argument(
        "--cache-dir",
        type=Path,
        default=_default_cache_dir(),
        help="Store cached OpenAI classifications here",
    )
    advanced = analyze.add_argument_group("Advanced config")
    advanced.add_argument(
        "--model",
        default=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        help=f"OpenAI model to use (default: {DEFAULT_OPENAI_MODEL} or OPENAI_MODEL)",
    )
    advanced.add_argument(
        "--openai-base-url",
        default=os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
        help=f"OpenAI-compatible API base URL (default: {DEFAULT_OPENAI_BASE_URL} or OPENAI_BASE_URL)",
    )
    advanced.add_argument(
        "--env-file",
        "--dotenv",
        dest="env_file",
        type=Path,
        default=Path(".env"),
        help="Read env vars from PATH instead of ./.env",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = _argv_list(argv)
    env_file, env_file_explicit = _resolve_env_file(raw_argv)
    if env_file_explicit and (not env_file.exists() or not env_file.is_file()):
        raise ConfigurationError(f"Env file not found: {env_file}")

    load_dotenv(env_file)
    args = build_parser().parse_args(raw_argv)

    if args.command == "analyze":
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        newsapi_key = os.environ.get("NEWSAPI_KEY", "").strip()

        ticker = str(args.ticker or "").strip().upper()
        if not ticker:
            raise ConfigurationError("Ticker cannot be empty.")
        if any(ch.isspace() for ch in ticker):
            raise ConfigurationError("Ticker cannot contain whitespace.")
        if len(ticker) > 24:
            raise ConfigurationError(
                "Ticker looks too long; expected a symbol like TSLA."
            )

        query = (args.query or ticker).strip()
        if not query:
            raise ConfigurationError("Query cannot be empty.")

        if int(args.days) < 1:
            raise ConfigurationError("--days must be >= 1.")
        if int(args.max_articles) < 1:
            raise ConfigurationError("--max-articles must be >= 1.")
        if float(args.half_life_hours) <= 0:
            raise ConfigurationError("--half-life-hours must be > 0.")
        if not args.no_cache and float(args.cache_ttl_hours) < 0:
            raise ConfigurationError("--cache-ttl-hours must be >= 0.")

        model = str(args.model or "").strip()
        if not model:
            raise ConfigurationError("--model cannot be empty.")

        openai_base_url = str(args.openai_base_url or "").strip()
        if not openai_base_url:
            raise ConfigurationError("--openai-base-url cannot be empty.")
        base_split = urlsplit(openai_base_url)
        if base_split.scheme not in {"http", "https"} or not base_split.netloc:
            raise ConfigurationError(
                "--openai-base-url must be an http(s) URL (e.g., https://api.openai.com/v1)."
            )

        now = datetime.now(timezone.utc)
        lookback_days = int(args.days)
        from_dt = now - timedelta(days=lookback_days)

        source_requested = args.source
        source_used = source_requested
        if source_used == "auto":
            source_used = "newsapi" if newsapi_key else "google-rss"
        if source_used == "newsapi" and not newsapi_key:
            raise ConfigurationError(
                "Missing NEWSAPI_KEY (required when --source=newsapi)."
            )

        if source_used == "newsapi":
            try:
                from_date = from_dt.date().isoformat()
                articles = fetch_everything(
                    api_key=newsapi_key, query=query, from_date=from_date, page_size=100
                )
            except RemoteApiError as e:
                if source_requested != "auto":
                    raise
                print(
                    f"NewsAPI request failed ({e}). Trying Google News RSS instead.",
                    file=sys.stderr,
                )
                source_used = "google-rss"
                articles = _fetch_google_news_rss_with_guidance(
                    query=query,
                    from_datetime=from_dt,
                    source_requested=source_requested,
                    newsapi_key_present=bool(newsapi_key),
                )
        else:
            articles = _fetch_google_news_rss_with_guidance(
                query=query,
                from_datetime=from_dt,
                source_requested=source_requested,
                newsapi_key_present=bool(newsapi_key),
            )

        unique = []
        seen = set()
        for a in articles:
            key = a.url or a.article_id
            if key in seen:
                continue
            seen.add(key)
            unique.append(a)
            if len(unique) >= max(1, int(args.max_articles)):
                break

        cache: JsonDiskCache | None = None
        ttl_seconds: float | None = None
        if not args.no_cache:
            ttl_seconds = float(args.cache_ttl_hours) * 3600.0
            try:
                cache = JsonDiskCache(
                    args.cache_dir,
                    warn=lambda message: print(message, file=sys.stderr),
                )
            except OSError as e:
                cache = None
                ttl_seconds = None
                print(f"Cache disabled: {e}", file=sys.stderr)

        if not openai_key and args.no_cache and unique:
            raise ConfigurationError(
                "Missing OPENAI_API_KEY. Set it to analyze articles, or rerun with caching enabled after a successful run."
            )

        try:
            summary = analyze_with_cache(
                ticker=ticker,
                query=query,
                articles=unique,
                cache=cache,
                cache_ttl_seconds=ttl_seconds,
                openai=OpenAISentimentConfig(
                    api_key=openai_key, model=model, base_url=openai_base_url
                ),
                include_reasons=bool(args.include_reasons),
                half_life_hours=float(args.half_life_hours),
            )
        except ConfigurationError as e:
            if not openai_key and "OPENAI_API_KEY" in str(e):
                raise ConfigurationError(
                    "Missing OPENAI_API_KEY. Some articles were not cached; set OPENAI_API_KEY to analyze them."
                ) from e
            raise

        if args.format == "json":
            payload = summary.to_dict(include_reasons=bool(args.include_reasons))
            payload["source"] = source_used
            payload["lookback_days"] = lookback_days
            if args.include_articles:
                payload["articles"] = [a.to_dict() for a in unique]
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                _format_text(summary, source=source_used, lookback_days=lookback_days)
            )
            if args.verbose:
                article_by_id = {a.article_id: a for a in unique}
                for r in summary.results:
                    a = article_by_id.get(r.article_id)
                    title = (a.title if a else "").strip()
                    source_name = (a.source if a else None) or ""
                    url = (a.url if a else None) or ""
                    reason = f" — {r.reason}" if r.reason else ""
                    print(
                        f"  {r.score:+.2f} conf={r.confidence:.2f} {r.label} {title} "
                        f"{'(' + source_name + ')' if source_name else ''} {url}{reason}".rstrip()
                    )

        return 0

    raise ConfigurationError(f"Unknown command: {args.command}")


def _entrypoint() -> None:
    try:
        raise SystemExit(main())
    except (ConfigurationError, RemoteApiError) as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(2)
    except StockSentimentError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        raise SystemExit(130)
