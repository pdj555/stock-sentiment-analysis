# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a stdlib-only Python CLI that fetches recent news for a stock ticker and uses the OpenAI API to classify each article's expected price impact over the next 1–5 trading days. It aggregates those classifications into a single sentiment score and trading signal.

## Setup and Dependencies

### Requirements
- Python >= 3.11
- No third-party runtime dependencies

### Environment Configuration
A `.env` file is optional in the project root. The CLI loads it by default (`--dotenv .env`) without overwriting existing environment variables.

Required:
```
OPENAI_API_KEY=your_api_key
```

Optional:
```
NEWSAPI_KEY=your_newsapi_key  # only for --source newsapi
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

## Running the Application

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
