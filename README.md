# Stock Sentiment Analysis

Score recent stock news sentiment with OpenAI.

## Quick Start

Set `OPENAI_API_KEY`, then run the CLI:

```bash
export OPENAI_API_KEY=...
python3 -m stock_sentiment analyze TSLA
```

If you want `--source auto` to prefer NewsAPI before falling back to Google News RSS, also set `NEWSAPI_KEY`.

Open the local UI:

```bash
python3 -m stock_sentiment ui
```

Set `OPENAI_API_KEY` first. Add `NEWSAPI_KEY` if you want auto to prefer NewsAPI.

Then visit `http://127.0.0.1:8765`.

## Configuration

You can keep secrets in the shell or in a local `./.env` file in your current working directory:

```bash
OPENAI_API_KEY=...
# Optional (only needed for --source newsapi; otherwise Google News RSS is used)
NEWSAPI_KEY=...
# Optional
OPENAI_MODEL=gpt-5-nano-2025-08-07
OPENAI_BASE_URL=https://api.openai.com/v1
```

When working in this repository, that usually means the repository root. Use `--env-file PATH` to read env vars from a different file instead of `./.env`.

## Installation

Optional console script:

```bash
python3 -m pip install -e .
```

## Deploy

### Fly.io

The included `Dockerfile` serves the UI on port `8080` with:

```bash
python -m stock_sentiment ui --host 0.0.0.0 --port 8080
```

Typical flow from the repository root:

```bash
fly launch --no-deploy
fly secrets set OPENAI_API_KEY=...
# Optional
fly secrets set NEWSAPI_KEY=...
fly deploy
```

### Vercel and other Python WSGI hosts

`app.py` exports the WSGI app as `app`, which keeps the same UI surface available to hosts that accept a Python WSGI entrypoint.

## Examples

Text summary:

```bash
python3 -m stock_sentiment analyze TSLA
```

JSON output with article reasons:

```bash
python3 -m stock_sentiment analyze TSLA --days 7 --max-articles 50 --format json --include-reasons
```

Force Google News RSS:

```bash
python3 -m stock_sentiment analyze TSLA --source google-rss
```

Notes:
- Default output is a single-line text summary; use `--format json` for structured output.
- By default `--source auto` uses NewsAPI when `NEWSAPI_KEY` is set, otherwise Google News RSS.
- In `--source auto`, if NewsAPI fails the CLI falls back to Google News RSS.
- If Google News RSS fails with a certificate or TLS error, check your local trust store or set `NEWSAPI_KEY` so `--source auto` can prefer NewsAPI.
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
