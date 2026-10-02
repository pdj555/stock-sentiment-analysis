# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a stdlib-only Python CLI that fetches recent news for a stock ticker and uses the OpenAI API to classify each article's expected price impact over the next 1–5 trading days. It aggregates those classifications into a single sentiment score and trading signal.

## Setup and Dependencies

### Requirements
- Python >= 3.11
- No third-party runtime dependencies

### Environment Configuration
A `.env` file is optional in the current working directory. The CLI loads `./.env` by default, or `--env-file FILE` to use a different file, without overwriting existing environment variables. In this repo that usually means the repository root.

Required (either works; OLLAMA wins when both are set):
```
OLLAMA_API_KEY=your_ollama_key
OPENAI_API_KEY=your_openai_key
```

Optional:
```
NEWSAPI_KEY=your_newsapi_key  # for --source newsapi, and lets --source auto prefer NewsAPI
OPENAI_MODEL=gpt-5.6-luna
OPENAI_BASE_URL=https://api.openai.com/v1
```

For Ollama Cloud (or any OpenAI-compatible endpoint), set `OLLAMA_API_KEY` and override the base URL and model. Ollama Cloud's OpenAI-compatible API lives at `https://ollama.com/v1` (no `api.` subdomain) and supports `/v1/responses` since Ollama v0.13.3; the client appends `/responses`. The model must be one Ollama hosts:
```
OLLAMA_API_KEY=your_ollama_key
OPENAI_BASE_URL=https://ollama.com/v1
OPENAI_MODEL=gpt-oss:120b
```

The Python CLI prefers `OLLAMA_*` over `OPENAI_*`.

### Model routing (web app)

The web app picks its provider from the active model id: a bare id (`gpt-oss:120b`) runs on Ollama Cloud; a `provider/model` id (`openai/gpt-5.6-luna`, `anthropic/claude-haiku-4-5`) runs on the Vercel AI Gateway. One knob selects it:
```
AI_MODEL=openai/gpt-5.6-luna            # default; Vercel AI Gateway (OpenAI)
# AI_MODEL=gpt-oss:120b                 # Ollama Cloud (bare id)
# AI_FALLBACK_MODEL=...                 # optional second route if the primary is capped/down
```
Ollama ids need `OLLAMA_API_KEY`; gateway ids authenticate with `AI_GATEWAY_API_KEY`, or automatically with `VERCEL_OIDC_TOKEN` on Vercel. Anonymous requests only ever use `AI_MODEL`. Unset `AI_MODEL` falls back to `OLLAMA_MODEL`, then `OPENAI_MODEL`, then `openai/gpt-5.6-luna`. Routing lives in `lib/server/providers.ts`. The Python CLI is unchanged (Ollama/OpenAI only).

### GitHub Actions secrets

Set per repository in GitHub → Settings → Secrets → Actions. Never paste keys into chat, commits, or shell history.

| Secret | Role |
| :-- | :-- |
| `CLAUDE_CODE_OAUTH_TOKEN` | Primary auth for `@claude` workflows |
| `OLLAMA_API_KEY` | Fallback when OAuth is unset |
| `ANTHROPIC_API_KEY` | Last-resort Anthropic API key |

Use `gh secret set SECRET_NAME -R pdj555/REPO` and enter the value at the prompt. Do not pipe from `.env` files.

Preferred:
```bash
python3 -m stock_sentiment analyze TSLA
```

Or install the console script:
```bash
python3 -m pip install -e .
stock-sentiment analyze TSLA
```

## Code Architecture

### Core Components

**`stock_sentiment/cli.py`**
- Argument parsing and user-facing behavior.

**`stock_sentiment/newsapi.py`** / **`stock_sentiment/google_rss.py`**
- News sources (NewsAPI requires `NEWSAPI_KEY`; Google RSS is the keyless fallback).

**`stock_sentiment/sentiment.py`**
- OpenAI prompting + JSON schema validation + aggregation into score/label/signal.

**`stock_sentiment/cache.py`**
- Simple disk cache for per-article OpenAI classifications.

## Development Notes

### Tests (offline)
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Tests must not perform real network calls.
