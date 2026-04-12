from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from stock_sentiment import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    __version__,
)
from stock_sentiment.env import load_dotenv
from stock_sentiment.errors import (
    ConfigurationError,
    RemoteApiError,
    StockSentimentError,
)
from stock_sentiment.runtime import (
    AnalysisRequest,
    default_cache_dir,
    display_source_name,
    run_analysis,
)
from stock_sentiment.types import SentimentSummary


def _format_text(
    summary: SentimentSummary,
    *,
    source_label: str,
    lookback_days: int,
    article_cap: int,
) -> str:
    score = f"{summary.score:+.3f}"
    conf = f"{summary.confidence:.2f}"
    as_of = summary.as_of.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    article_word = "article" if summary.articles_analyzed == 1 else "articles"
    rendered = (
        f"{summary.ticker} sentiment {score} ({summary.label}, confidence {conf}), "
        f"signal {summary.signal}, from {summary.articles_analyzed} {article_word} "
        f"out of a {article_cap}-article cap using {source_label} "
        f"over a {lookback_days}-day lookback as of {as_of}"
    )
    if summary.classification_degraded and summary.classification_warnings:
        rendered += f" Warning: {' '.join(summary.classification_warnings)}"
    return rendered


def _argv_list(argv: list[str] | None) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)


def _resolve_env_file(argv: list[str]) -> tuple[Path, bool]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--env-file", dest="env_file", type=Path, metavar="FILE")
    parser.add_argument("--dotenv", dest="env_file", type=Path, help=argparse.SUPPRESS)
    parsed, _ = parser.parse_known_args(argv)
    env_file = parsed.env_file or Path(".env")
    return env_file, parsed.env_file is not None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stock-sentiment",
        description="Score recent stock news sentiment from the CLI or a local web UI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  stock-sentiment analyze TSLA\n"
            "  stock-sentiment analyze TSLA --format json --include-reasons\n"
            "  stock-sentiment analyze TSLA --source google-rss --days 7\n"
            "  stock-sentiment ui\n"
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
            "  --env-file FILE reads env vars from FILE instead of ./.env in the current working directory.\n"
        ),
    )
    analyze.add_argument("ticker", help="Stock ticker symbol (e.g., TSLA)")
    analyze.add_argument(
        "--query",
        help="Search phrase used to find articles; defaults to the ticker symbol.",
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
        default=default_cache_dir(),
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
        dest="env_file",
        type=Path,
        metavar="FILE",
        default=Path(".env"),
        help="Read env vars from FILE instead of ./.env",
    )
    advanced.add_argument(
        "--dotenv",
        dest="env_file",
        type=Path,
        help=argparse.SUPPRESS,
    )

    ui = sub.add_parser(
        "ui",
        help="Start the local web UI",
        description="Open a local web UI for one-ticker sentiment checks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Quick start:\n"
            "  export OPENAI_API_KEY=...\n"
            "  stock-sentiment ui\n\n"
            "Notes:\n"
            "  Add NEWSAPI_KEY if you want auto to prefer NewsAPI.\n"
            "  --env-file FILE reads env vars from FILE instead of ./.env in the current working directory.\n"
            "  For container hosts, bind 0.0.0.0 and use the platform port.\n"
        ),
    )
    ui.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the local UI (default: 127.0.0.1)",
    )
    ui.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for the local UI (default: 8765)",
    )
    ui.add_argument(
        "--env-file",
        dest="env_file",
        type=Path,
        metavar="FILE",
        default=Path(".env"),
        help="Read env vars from FILE instead of ./.env",
    )
    ui.add_argument(
        "--dotenv",
        dest="env_file",
        type=Path,
        help=argparse.SUPPRESS,
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = _argv_list(argv)
    env_file, env_file_explicit = _resolve_env_file(raw_argv)
    if env_file_explicit and (not env_file.exists() or not env_file.is_file()):
        raise ConfigurationError(f"Env file not found: {env_file}")

    load_dotenv(env_file)
    args = build_parser().parse_args(raw_argv)

    if args.command == "ui":
        host = str(args.host or "").strip()
        if not host:
            raise ConfigurationError("--host cannot be empty.")
        port = int(args.port)
        if port < 1 or port > 65535:
            raise ConfigurationError("--port must be between 1 and 65535.")

        from stock_sentiment.ui import run_ui_server

        run_ui_server(host=host, port=port)
        return 0

    if args.command == "analyze":
        if args.include_reasons and args.format == "text" and not args.verbose:
            raise ConfigurationError(
                "--include-reasons requires --verbose or --format json."
            )
        result = run_analysis(
            AnalysisRequest(
                ticker=args.ticker,
                query=args.query,
                lookback_days=int(args.days),
                max_articles=int(args.max_articles),
                half_life_hours=float(args.half_life_hours),
                source=args.source,
                openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
                newsapi_key=os.environ.get("NEWSAPI_KEY", "").strip(),
                openai_model=str(args.model or ""),
                openai_base_url=str(args.openai_base_url or ""),
                use_cache=not args.no_cache,
                cache_ttl_hours=float(args.cache_ttl_hours),
                cache_dir=args.cache_dir,
                include_reasons=bool(args.include_reasons),
            ),
            warn=lambda message: print(message, file=sys.stderr),
        )
        summary = result.summary
        source_used = result.source
        source_label = display_source_name(source_used)
        unique = result.articles
        lookback_days = result.lookback_days
        article_cap = result.article_cap

        if args.format == "json":
            payload = summary.to_dict(include_reasons=bool(args.include_reasons))
            payload["source"] = source_used
            payload["source_label"] = source_label
            payload["lookback_days"] = lookback_days
            payload["article_cap"] = article_cap
            if args.include_articles:
                payload["articles"] = [a.to_dict() for a in unique]
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                _format_text(
                    summary,
                    source_label=source_label,
                    lookback_days=lookback_days,
                    article_cap=article_cap,
                )
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
