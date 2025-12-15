# Stock Sentiment Analysis

Fetch recent news for a ticker and compute a sentiment score using the OpenAI API.

## Setup

1. Create a local `.env` file (optional) in the project root:

```bash
OPENAI_API_KEY=...
# Optional (only needed for --source newsapi; otherwise Google News RSS is used)
NEWSAPI_KEY=...
# Optional
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

2. (Optional) Install a CLI entrypoint:

```bash
python3 -m pip install -e .
```

3. Run an analysis:

```bash
python3 -m stock_sentiment analyze TSLA
python3 -m stock_sentiment analyze TSLA --days 7 --max-articles 50 --format json --include-reasons
python3 -m stock_sentiment analyze TSLA --source google-rss
```

Notes:
- Default output is a single-line text summary; use `--format json` for structured output.
- By default `--source auto` uses NewsAPI when `NEWSAPI_KEY` is set, otherwise Google News RSS.
- In `--source auto`, if NewsAPI fails the CLI falls back to Google News RSS.
- `OPENAI_API_KEY` is required unless all needed per-article classifications are already cached.
- Add `--include-articles` to embed article metadata in JSON output.
- Add `--verbose` to print per-article sentiment details in text mode.
- OpenAI results are cached locally by default (see `--cache-dir`, `--no-cache`, `--cache-ttl-hours`).
- JSON output includes `source` and `lookback_days` fields for downstream systems.

Disclaimer: This tool is for informational purposes only and is not financial advice.

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```
