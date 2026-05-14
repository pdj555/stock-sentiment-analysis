# Stock Sentiment Analysis

Score recent stock news sentiment with OpenAI. The default model is `gpt-5.4-nano`, chosen for high-volume classification based on current OpenAI model guidance; override `OPENAI_MODEL` when you want a larger model.

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
# Optional (needed for --source newsapi, and lets --source auto prefer NewsAPI)
NEWSAPI_KEY=...
# Optional
OPENAI_MODEL=gpt-5.4-nano
OPENAI_BASE_URL=https://api.openai.com/v1
```

When working in this repository, that usually means the repository root. Use `--env-file FILE` to read env vars from a different file instead of `./.env`.

## Installation

Editable install (adds the `stock-sentiment` command):

```bash
python3 -m pip install -e .
stock-sentiment analyze TSLA
```

## Deploy

### Fly.io

The included `Dockerfile` serves the UI on port `8080` with:

```bash
python -m stock_sentiment ui --host 0.0.0.0 --port 8080
```

Typical flow from the repository root:

```bash
fly launch --generate-name --internal-port 8080 --no-deploy
fly secrets set OPENAI_API_KEY=...
# Optional
fly secrets set NEWSAPI_KEY=...
fly deploy
```

### Vercel

Vercel builds the project with the Python runtime: `requirements.txt` marks it as a Python app (no third-party runtime dependencies), and `.vercelignore` keeps the deployment a clean Python project so the Node development tooling does not shadow that detection. The Serverless Function lives at `api/index.py` (Vercel only treats files inside `api/` as functions); it re-exports the WSGI `app` from `stock_sentiment.ui`. The `rewrites` rule in `vercel.json` sends every path to that function, and the function is given a 60-second maximum duration. On Vercel, the UI cache is written to `/tmp/stock_sentiment`, which is suitable for ephemeral serverless function storage.

Typical flow from the repository root:

```bash
vercel env add OPENAI_API_KEY preview
vercel env add OPENAI_API_KEY production
# Optional
vercel env add NEWSAPI_KEY preview
vercel env add NEWSAPI_KEY production
vercel deploy
vercel deploy --prod
```

### Other Python WSGI hosts

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
- Use `--include-articles` with `--format json` to embed article metadata.
- Use `--include-reasons` with `--format json` or `--verbose`.
- Add `--verbose` to print per-article sentiment details in text mode.
- OpenAI results are cached locally by default (see `--cache-dir`, `--no-cache`, `--cache-ttl-hours`).
- If OpenAI returns partial classifications, the CLI and UI flag the run as degraded instead of presenting a clean-looking neutral result.
- JSON output includes `source`, `source_label`, `lookback_days`, `article_cap`, `classification_degraded`, and `classification_warnings` fields for downstream systems.

Disclaimer: This tool is for informational purposes only and is not financial advice.

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Optional browser smoke test for the local UI (no API keys needed):

This starts a local fixture server and drives the browser through the happy path.

```bash
npm install
npx playwright install --with-deps chromium
npx playwright test tests/test_ui_browser.spec.js --reporter=line --output=output/playwright/test-results
```
