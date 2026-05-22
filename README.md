# Stock Sentiment Analysis

Recent equity news, classified and summarized. CLI, Next.js app, deployable to Vercel or Fly.

```mermaid
flowchart LR
  T[Ticker] --> N[News]
  N --> C[Classify]
  C --> S[Sentiment]
  S --> O[CLI · Web]
```

## Get started

```bash
export OPENAI_API_KEY=...

python3 -m pip install -e .
python3 -m stock_sentiment analyze TSLA
```

Web app:

```bash
npm install && npm run dev   # http://localhost:3000
```

## Overview

| Surface | Entry |
| :-- | :-- |
| CLI | `python3 -m stock_sentiment analyze TSLA` |
| Next.js | `npm run dev` |
| Python UI | `python3 -m stock_sentiment ui` |

News sources: NewsAPI when `NEWSAPI_KEY` is set, otherwise Google News RSS. Partial classification failures are reported as degraded runs — not silent neutral scores.

JSON output:

```bash
python3 -m stock_sentiment analyze TSLA --format json --include-reasons
```

## Reference

| Variable | Role |
| :-- | :-- |
| `OPENAI_API_KEY` | Required for classification |
| `NEWSAPI_KEY` | Optional; preferred in `--source auto` |
| `OPENAI_MODEL` | Override model (see repo defaults) |

**Test.**

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Informational use only. Not financial advice.

MIT · [LICENSE](LICENSE)
