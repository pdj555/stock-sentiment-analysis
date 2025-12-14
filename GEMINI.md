# Stock Sentiment Analysis Tool

## Project Context
This is a stdlib-only Python utility that analyzes the sentiment of recent news articles for specific stock tickers. It can fetch news via NewsAPI (optional) or Google News RSS (fallback) and uses the OpenAI API to classify each article's expected price impact. It then aggregates those classifications into a single sentiment score and trading signal.

## Technology Stack
*   **Language:** Python
*   **HTTP:** `urllib` (standard library)
*   **Configuration:** local `.env` loader (standard library)
*   **APIs:** OpenAI (required), NewsAPI (optional)

## Setup & Installation

1.  **Environment Configuration:**
    Create a `.env` file in the project root (optional):
    ```ini
    OPENAI_API_KEY=your_api_key_here
    # Optional (only needed for --source newsapi)
    NEWSAPI_KEY=your_newsapi_key_here
    # Optional
    OPENAI_MODEL=gpt-4o-mini
    OPENAI_BASE_URL=https://api.openai.com/v1
    ```

## Usage

To run the analysis:

```bash
python3 -m stock_sentiment analyze TSLA
```

## Code Structure

*   **`stock_sentiment/cli.py`**: CLI entrypoint.
*   **`stock_sentiment/sentiment.py`**: OpenAI classification + aggregation.
*   **`stock_sentiment/newsapi.py`**: NewsAPI client.
*   **`stock_sentiment/google_rss.py`**: Google News RSS fallback.
*   **`stock_sentiment/cache.py`**: Disk caching of OpenAI classifications.
*   **`settings.py`**: Convenience helpers for env vars and `.env` loading.

## Development Conventions

*   **Testing:** Standard library `unittest`, no network calls.
    ```bash
    python3 -m unittest discover -s tests -p "test_*.py"
    ```
