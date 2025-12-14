# Repository Guidelines

## Project Structure & Module Organization

- `stock_sentiment/`: Production code (CLI, NewsAPI client, OpenAI client, caching, scoring).
- `main.py`: Backward-compatible entrypoint (delegates to the CLI).
- `settings.py`: Lightweight `.env` loader and env var access helpers (no external deps).
- `tests/`: Unit tests (`unittest`, no network calls).
- `.github/workflows/ci.yml`: CI that runs tests on multiple Python versions.
- `.env` (local only): Stores secrets; ignored by Git (see `.gitignore`).
- `.agent/`: Automation settings and extended improvement guidance (see `.agent/instructions.md`).
- Docs: `README.md`, `CLAUDE.md`, `GEMINI.md`.

## Build, Test, and Development Commands

Typical local setup/run (macOS/Linux):

```bash
python3 -m venv .venv
source .venv/bin/activate
export OPENAI_API_KEY=...
export NEWSAPI_KEY=...
python3 -m stock_sentiment analyze TSLA
```

- `python3 -m stock_sentiment analyze TSLA`: Fetches recent articles and outputs a sentiment summary.
- `--format json --include-reasons`: Produces structured output suitable for downstream trading systems.
- `--no-cache` / `--cache-dir`: Control local caching of OpenAI classifications (cost/latency control).

## Coding Style & Naming Conventions

- Follow PEP 8: 4-space indentation, `snake_case` for functions/variables, and minimal top-level side effects.
- Keep changes small and readable; prefer clear function boundaries for fetching, analysis, and scoring.
- No formatter/linter is configured in this repo today—if you introduce one, document it in `README.md`.

## Testing Guidelines

- Tests use the standard library `unittest` and must not require network access.
- Run: `python3 -m unittest discover -s tests -p "test_*.py"`

## Commit & Pull Request Guidelines

- Commit history trends toward short, imperative messages (e.g., `Update README.md`, `Reorganized repository`, `Fixed software. Now functioning.`).
- PRs should include: what changed, how to run/verify locally, and any dependency or behavior changes (update `README.md` when applicable).

## Configuration & Security

- Never commit secrets. Use environment variables or a local `.env` (ignored by Git).
- Required: `OPENAI_API_KEY`. Optional: `NEWSAPI_KEY` (only for `--source newsapi`), `OPENAI_MODEL`, `OPENAI_BASE_URL`.
- Be mindful of API rate limits and failures; keep error messages actionable and avoid logging keys.
