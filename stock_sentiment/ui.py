from __future__ import annotations

import json
import os
import sys
import traceback
from collections.abc import Callable, Iterable
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

from stock_sentiment import DEFAULT_OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL
from stock_sentiment.errors import ConfigurationError, ParseError, RemoteApiError
from stock_sentiment.runtime import (
    AnalysisRequest,
    AnalysisRunResult,
    default_cache_dir,
    display_source_name,
    run_analysis,
)

UI_HOST = "127.0.0.1"
UI_PORT = 8765
UI_LOOKBACK_DAYS = 3
UI_MAX_ARTICLES = 18
UI_HALF_LIFE_HOURS = 24.0
UI_CACHE_TTL_SECONDS = 24.0 * 3600.0

UI_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Sentiment</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Ubuntu+Mono:wght@700&display=swap" rel="stylesheet">
    <style>
      :root {
        color-scheme: dark;
        --backdrop: #05080c;
        --bg-raise: #0a0f14;
        --bg-elevated: #0d1218;
        --plain: #ffffff;
        --primary: #a9daf7;
        --primary-dim: #1769ff;
        --grid: rgba(60, 60, 60, 0.55);
        --text: #f5f5f5;
        --muted: #8b949e;
        --faint: #5c6370;
        --border: rgba(169, 218, 247, 0.14);
        --positive: #6ee7b7;
        --negative: #fca5a5;
        --neutral: var(--primary);
        --mono: "Ubuntu Mono", ui-monospace, monospace;
        --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      }

      * {
        box-sizing: border-box;
      }

      html,
      body {
        margin: 0;
        min-height: 100%;
        background: var(--backdrop);
        color: var(--primary);
        font-family: var(--mono);
        font-size: 16px;
      }

      body::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -1;
        pointer-events: none;
        background-color: var(--backdrop);
        background-image:
          linear-gradient(var(--grid) 1px, transparent 1px),
          linear-gradient(90deg, var(--grid) 1px, transparent 1px);
        background-size: 48px 48px;
      }

      a {
        color: inherit;
      }

      .nav {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        align-items: center;
        gap: 12px;
        max-width: 1180px;
        margin: 0 auto;
        padding: 18px 16px 8px;
      }

      .nav-left {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .nav-meta {
        font-family: var(--mono);
        font-size: 12px;
        color: var(--plain);
        text-transform: lowercase;
      }

      .nav-meta-sep {
        color: var(--faint);
      }

      .brand {
        font-family: var(--mono);
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.04em;
        color: var(--plain);
        text-align: center;
      }

      .nav-tag {
        font-family: var(--mono);
        font-size: 12px;
        color: var(--plain);
        text-transform: lowercase;
        text-align: right;
      }

      main {
        max-width: 1180px;
        margin: 0 auto;
        padding: 8px 16px 48px;
        text-align: left;
      }

      .hero-panel {
        border: 2px solid var(--primary);
        border-radius: 6px;
        padding: clamp(20px, 4vw, 32px);
      }

      .nous-title {
        margin: 0;
        font-family: var(--mono);
        font-weight: 700;
        font-size: clamp(2.75rem, 11vw, 4.25rem);
        line-height: 0.92;
        letter-spacing: -0.03em;
        color: transparent;
        background-image: repeating-linear-gradient(
          180deg,
          #a9daf7 0,
          #a9daf7 5px,
          rgba(5, 8, 12, 0.92) 5px,
          rgba(5, 8, 12, 0.92) 10px
        );
        -webkit-background-clip: text;
        background-clip: text;
      }

      .nous-section {
        margin: 14px 0 0;
        font-family: var(--mono);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--primary);
      }

      h1.hero-prompt {
        margin: 4px 0 0;
        max-width: 28ch;
        font-family: var(--sans);
        font-size: clamp(1.05rem, 2.4vw, 1.25rem);
        font-weight: 400;
        line-height: 1.35;
        letter-spacing: -0.02em;
        color: var(--plain);
      }

      .form-row {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 16px;
        max-width: 560px;
        padding: 10px 12px;
        border: 2px solid var(--primary);
        border-radius: 6px;
        background: var(--bg-raise);
      }

      label {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
      }

      input {
        flex: 1;
        min-width: 0;
        border: 0;
        background: transparent;
        outline: none;
        color: var(--plain);
        font-family: var(--mono);
        font-size: 14px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }

      input::placeholder {
        color: var(--faint);
      }

      button[type="submit"] {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 34px;
        height: 34px;
        min-width: 34px;
        border: 2px solid var(--primary);
        border-radius: 6px;
        padding: 0;
        background: transparent;
        color: var(--primary);
        font-size: 13px;
        font-weight: 700;
        cursor: pointer;
      }

      button[type="submit"]:disabled {
        opacity: 0.45;
        cursor: wait;
      }

      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 16px;
      }

      .chip {
        padding: 6px 12px;
        border: 2px solid var(--primary);
        border-radius: 6px;
        background: transparent;
        color: var(--primary);
        font-family: var(--mono);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.06em;
        cursor: pointer;
      }

      .chip:hover:not(:disabled) {
        background: var(--primary);
        color: var(--backdrop);
      }

      .status-line {
        min-height: 20px;
        margin: 16px 0 0;
        font-family: var(--mono);
        font-size: 14px;
        color: var(--primary-dim);
        text-transform: lowercase;
      }

      .status-line.loading {
        animation: pulse 1.6s ease-in-out infinite;
      }

      @keyframes pulse {
        0%, 100% { opacity: 0.45; }
        50% { opacity: 1; }
      }

      .results {
        margin-top: 32px;
        text-align: left;
      }

      .state {
        min-height: 48px;
        color: var(--muted);
        font-size: 14px;
      }

      .state.error {
        padding: 14px 16px;
        border: 1px solid rgba(252, 165, 165, 0.2);
        border-radius: 8px;
        color: var(--negative);
        background: rgba(252, 165, 165, 0.04);
      }

      .summary-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0;
        border: 2px solid var(--primary);
        border-radius: 4px;
        background: var(--bg-raise);
        overflow: hidden;
        animation: rise 0.24s ease;
      }

      .summary-warning {
        margin: 14px 0 0;
        padding: 12px 14px;
        border: 1px solid var(--border);
        border-radius: 4px;
        font-size: 13px;
        line-height: 1.5;
        color: var(--muted);
        background: rgba(169, 218, 247, 0.03);
      }

      .metric {
        min-width: 0;
        padding: 14px 16px;
        border-right: 1px solid var(--border);
      }

      .metric:last-child {
        border-right: 0;
      }

      .metric dt {
        margin: 0;
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--primary);
      }

      .metric dd {
        margin: 6px 0 0;
        font-family: var(--mono);
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.2;
        color: var(--plain);
      }

      .articles {
        list-style: none;
        margin: 16px 0 0;
        padding: 0;
        border: 2px solid var(--primary);
        border-radius: 4px;
        background: var(--bg-raise);
        overflow: hidden;
      }

      .article {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 14px;
        padding: 16px 18px;
        border-bottom: 1px solid var(--border);
        animation: rise 0.24s ease;
      }

      .article:last-child {
        border-bottom: 0;
      }

      .article-title {
        margin: 0;
        font-size: 14px;
        line-height: 1.45;
        font-weight: 500;
      }

      .article-title a {
        text-decoration: none;
      }

      .article-title a:hover {
        color: var(--primary);
      }

      .article-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 12px;
        margin-top: 8px;
        font-family: var(--mono);
        font-size: 11px;
        color: var(--faint);
      }

      .article-reason {
        max-width: 64ch;
        margin-top: 8px;
        font-size: 13px;
        line-height: 1.55;
        color: var(--muted);
      }

      .badge {
        align-self: start;
        border-radius: 4px;
        padding: 3px 8px;
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        border: 1px solid var(--border);
        background: rgba(169, 218, 247, 0.03);
      }

      .badge.positive { color: var(--positive); }
      .badge.negative { color: var(--negative); }
      .badge.neutral { color: var(--neutral); }

      .footer {
        margin-top: 24px;
        color: var(--faint);
        font-size: 11px;
        text-align: center;
        text-transform: lowercase;
      }

      @keyframes rise {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }

      @media (max-width: 820px) {
        .summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .metric:nth-child(3) { border-right: 0; }
      }

      @media (max-width: 680px) {
        main { padding: 32px 16px 48px; }
        .form-row { flex-wrap: wrap; border-radius: 12px; }
        input { flex-basis: 100%; padding: 4px 8px; }
        button[type="submit"] { width: 100%; border-radius: 8px; }
        .article { grid-template-columns: minmax(0, 1fr); }
        .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
    </style>
  </head>
  <body>
    <header class="nav">
      <div class="nav-left">
        <span class="nav-meta">lookback: 3d</span>
        <span class="nav-meta-sep">·</span>
        <span class="nav-meta">news + rss</span>
      </div>
      <div class="brand">Sentiment</div>
      <span class="nav-tag">research preview</span>
    </header>

    <main>
      <section class="hero-panel">
        <h1 class="nous-title">Sentiment</h1>
        <p class="nous-section">Ticker query</p>
        <h2 class="hero-prompt">What ticker should we read?</h2>

        <form id="analyze-form" class="form-row">
        <label for="ticker">Ticker</label>
        <input
          id="ticker"
          name="ticker"
          placeholder="Enter a ticker"
          autocomplete="off"
          autocapitalize="characters"
          spellcheck="false"
          maxlength="24"
        >
        <button id="submit-button" type="submit" aria-label="Analyze">↑</button>
      </form>

      <div class="chips" id="chips">
        <button type="button" class="chip" data-ticker="AAPL">AAPL</button>
        <button type="button" class="chip" data-ticker="NVDA">NVDA</button>
        <button type="button" class="chip" data-ticker="TSLA">TSLA</button>
        <button type="button" class="chip" data-ticker="AMD">AMD</button>
      </div>

      <p id="status-line" class="status-line"></p>
      </section>

      <section class="results" aria-live="polite">
        <div id="summary" class="state"></div>
        <ul id="articles" class="articles"></ul>
      </section>

      <p class="footer">for research only — not financial advice</p>
    </main>

    <script>
      const form = document.getElementById("analyze-form");
      const tickerInput = document.getElementById("ticker");
      const submitButton = document.getElementById("submit-button");
      const statusLine = document.getElementById("status-line");
      const summary = document.getElementById("summary");
      const articles = document.getElementById("articles");
      const chips = document.getElementById("chips");

      chips.addEventListener("click", (event) => {
        const button = event.target.closest("[data-ticker]");
        if (!button || submitButton.disabled) {
          return;
        }
        const symbol = button.getAttribute("data-ticker");
        tickerInput.value = symbol;
        analyzeTicker(symbol);
      });

      function escapeHtml(value) {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");
      }

      function formatScore(value) {
        const number = Number(value ?? 0);
        if (!Number.isFinite(number)) {
          return "0.000";
        }
        return number > 0 ? `+${number.toFixed(3)}` : number.toFixed(3);
      }

      function formatConfidence(value) {
        const number = Number(value ?? 0);
        if (!Number.isFinite(number)) {
          return "0.00";
        }
        return number.toFixed(2);
      }

      function formatTime(value) {
        if (!value) {
          return "";
        }

        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
          return "";
        }

        return new Intl.DateTimeFormat(undefined, {
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
          timeZoneName: "short",
        }).format(date);
      }

      function renderIdle(message) {
        summary.className = "state";
        summary.textContent = message;
        articles.innerHTML = "";
      }

      function renderError(message) {
        summary.className = "state error";
        summary.textContent = message;
        articles.innerHTML = "";
      }

      function renderSummary(summaryData) {
        const warningText = Array.isArray(summaryData.classification_warnings)
          ? summaryData.classification_warnings.join(" ")
          : "";
        const warningHtml = summaryData.classification_degraded && warningText
          ? `<p class="summary-warning">${escapeHtml(warningText)}</p>`
          : "";
        const html = `
          <dl class="summary-grid">
            <div class="metric">
              <dt>Ticker</dt>
              <dd>${escapeHtml(summaryData.ticker)}</dd>
            </div>
            <div class="metric">
              <dt>Signal</dt>
              <dd>${escapeHtml(summaryData.signal)}</dd>
            </div>
            <div class="metric">
              <dt>Score</dt>
              <dd>${escapeHtml(formatScore(summaryData.score))}</dd>
            </div>
            <div class="metric">
              <dt>Confidence</dt>
              <dd>${escapeHtml(formatConfidence(summaryData.confidence))}</dd>
            </div>
            <div class="metric">
              <dt>Articles</dt>
              <dd>${escapeHtml(summaryData.articles_analyzed)}</dd>
            </div>
          </dl>
          ${warningHtml}
        `;

        summary.className = "";
        summary.innerHTML = html;
      }

      function renderArticles(items) {
        if (!items.length) {
          articles.innerHTML = "";
          return;
        }

        articles.innerHTML = items
          .map((item) => {
            const title = escapeHtml(item.title || "Untitled article");
            const href = item.url ? escapeHtml(item.url) : "";
            const source = item.source ? escapeHtml(item.source) : "Unknown source";
            const publishedAt = formatTime(item.published_at);
            const score = escapeHtml(formatScore(item.score));
            const label = escapeHtml(item.label || "neutral");
            const reason = item.reason ? `<p class="article-reason">${escapeHtml(item.reason)}</p>` : "";
            const titleHtml = href
              ? `<a href="${href}" target="_blank" rel="noreferrer">${title}</a>`
              : title;

            return `
              <li class="article">
                <div>
                  <h2 class="article-title">${titleHtml}</h2>
                  <div class="article-meta">
                    <span>${source}</span>
                    ${publishedAt ? `<span>${escapeHtml(publishedAt)}</span>` : ""}
                    <span>${score}</span>
                  </div>
                  ${reason}
                </div>
                <div class="badge ${label}">${label}</div>
              </li>
            `;
          })
          .join("");
      }

      async function analyzeTicker(ticker) {
        submitButton.disabled = true;
        chips.querySelectorAll(".chip").forEach((chip) => {
          chip.disabled = true;
        });
        statusLine.textContent = "loading...";
        statusLine.className = "status-line loading";

        try {
          const response = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker }),
          });

          const payload = await response.json();
          if (!response.ok) {
            throw new Error(payload.error?.message || "The request failed.");
          }

          renderSummary(payload.summary);
          renderArticles(payload.articles || []);

          const asOf = formatTime(payload.summary.as_of);
          const sourceLabel =
            payload.summary.source_label || payload.summary.source || "source unavailable";
          const windowDays = payload.summary.lookback_days || 3;
          const articleCap = Number(payload.summary.article_cap || 0);
          const analyzed = Number(payload.summary.articles_analyzed || 0);
          const coverage = articleCap > 0
            ? ` - ${analyzed} of ${articleCap} articles analyzed`
            : "";
          statusLine.className = "status-line";
          statusLine.textContent = asOf
            ? `${sourceLabel} - ${windowDays}-day lookback${coverage} - as of ${asOf}`
            : `${sourceLabel} - ${windowDays}-day lookback${coverage}`;
        } catch (error) {
          const message = error && error.message
            ? error.message
            : "The analysis could not load. Check your connection or restart the server, then try again.";
          renderError(message);
          statusLine.className = "status-line";
          statusLine.textContent = message;
        } finally {
          submitButton.disabled = false;
          chips.querySelectorAll(".chip").forEach((chip) => {
            chip.disabled = false;
          });
        }
      }

      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const ticker = tickerInput.value.trim().toUpperCase();
        if (!ticker) {
          renderError("Ticker cannot be empty.");
          statusLine.className = "status-line";
          statusLine.textContent = "enter a ticker.";
          tickerInput.focus();
          return;
        }

        analyzeTicker(ticker);
      });

      tickerInput.addEventListener("input", () => {
        if (summary.classList.contains("error")) {
          summary.className = "state";
          summary.textContent = "";
          statusLine.textContent = "";
        }
      });
    </script>
  </body>
</html>
"""


def _display_source_name(source: str) -> str:
    return display_source_name(source)


def ui_cache_dir() -> Path:
    if os.environ.get("VERCEL"):
        return Path("/tmp") / "stock_sentiment"
    return default_cache_dir()


def run_ui_analysis(ticker: str) -> AnalysisRunResult:
    try:
        return run_analysis(
            AnalysisRequest(
                ticker=ticker,
                lookback_days=UI_LOOKBACK_DAYS,
                max_articles=UI_MAX_ARTICLES,
                half_life_hours=UI_HALF_LIFE_HOURS,
                source="auto",
                openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
                newsapi_key=os.environ.get("NEWSAPI_KEY", "").strip(),
                openai_model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
                openai_base_url=os.environ.get(
                    "OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL
                ),
                use_cache=True,
                cache_ttl_hours=UI_CACHE_TTL_SECONDS / 3600.0,
                cache_dir=ui_cache_dir(),
                include_reasons=True,
            ),
            warn=lambda message: print(message, file=sys.stderr),
        )
    except ConfigurationError as e:
        if "OPENAI_API_KEY" in str(e):
            raise ConfigurationError(
                "Missing OPENAI_API_KEY. Set it in your shell or ./.env, then try again."
            ) from e
        raise


def _build_response_payload(result: AnalysisRunResult) -> dict[str, object]:
    results_by_id = {item.article_id: item for item in result.summary.results}

    articles_payload: list[dict[str, object]] = []
    for article in result.articles:
        sentiment = results_by_id.get(article.article_id)
        articles_payload.append(
            {
                "article_id": article.article_id,
                "title": article.title,
                "description": article.description,
                "url": article.url,
                "source": article.source,
                "published_at": article.published_at.isoformat()
                if article.published_at
                else None,
                "label": sentiment.label if sentiment else "neutral",
                "score": sentiment.score if sentiment else 0.0,
                "confidence": sentiment.confidence if sentiment else 0.0,
                "reason": sentiment.reason if sentiment else None,
            }
        )

    return {
        "summary": {
            "ticker": result.summary.ticker,
            "signal": result.summary.signal,
            "label": result.summary.label,
            "score": result.summary.score,
            "confidence": result.summary.confidence,
            "articles_analyzed": result.summary.articles_analyzed,
            "classification_degraded": result.summary.classification_degraded,
            "classification_warnings": list(result.summary.classification_warnings),
            "as_of": result.summary.as_of.isoformat(),
            "source": result.source,
            "source_label": _display_source_name(result.source),
            "lookback_days": result.lookback_days,
            "article_cap": result.article_cap,
        },
        "articles": articles_payload,
    }


def _response(
    start_response: Callable[[str, list[tuple[str, str]]], object],
    *,
    status: str,
    body: bytes,
    content_type: str,
) -> Iterable[bytes]:
    start_response(
        status,
        [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ],
    )
    return [body]


def _json_response(
    start_response: Callable[[str, list[tuple[str, str]]], object],
    *,
    status: str,
    payload: dict[str, object],
) -> Iterable[bytes]:
    return _response(
        start_response,
        status=status,
        content_type="application/json; charset=utf-8",
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def _html_response(
    start_response: Callable[[str, list[tuple[str, str]]], object]
) -> Iterable[bytes]:
    return _response(
        start_response,
        status="200 OK",
        content_type="text/html; charset=utf-8",
        body=UI_HTML.encode("utf-8"),
    )


def _read_json_body(environ: dict[str, object]) -> dict[str, object]:
    raw_length = str(environ.get("CONTENT_LENGTH") or "0")
    try:
        content_length = max(0, int(raw_length))
    except ValueError as e:
        raise ConfigurationError("Request body length was invalid.") from e

    body_stream = environ.get("wsgi.input")
    if body_stream is None or not hasattr(body_stream, "read"):
        raise ConfigurationError("Request body was missing.")

    raw_body = body_stream.read(content_length)
    if not raw_body:
        return {}

    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ConfigurationError(
            'Request body must be valid JSON like {"ticker":"TSLA"}.'
        ) from e

    if not isinstance(parsed, dict):
        raise ConfigurationError(
            'Request body must be a JSON object like {"ticker":"TSLA"}.'
        )
    return parsed


def create_app(
    analyze_func: Callable[[str], AnalysisRunResult] = run_ui_analysis,
) -> Callable[[dict[str, object], Callable[[str, list[tuple[str, str]]], object]], Iterable[bytes]]:
    def application(
        environ: dict[str, object],
        start_response: Callable[[str, list[tuple[str, str]]], object],
    ) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD") or "GET").upper()
        path = str(environ.get("PATH_INFO") or "/")

        if method == "GET" and path in {"", "/"}:
            return _html_response(start_response)

        if method == "GET" and path == "/health":
            return _json_response(
                start_response,
                status="200 OK",
                payload={"ok": True},
            )

        if method == "GET" and path == "/favicon.ico":
            return _response(
                start_response,
                status="204 No Content",
                content_type="image/x-icon",
                body=b"",
            )

        if method == "POST" and path == "/api/analyze":
            try:
                body = _read_json_body(environ)
                raw_ticker = body.get("ticker", "")
                if not isinstance(raw_ticker, str):
                    raise ConfigurationError('Ticker must be a string like "TSLA".')
                ticker = raw_ticker.strip()
                result = analyze_func(ticker)
                return _json_response(
                    start_response,
                    status="200 OK",
                    payload=_build_response_payload(result),
                )
            except ConfigurationError as e:
                return _json_response(
                    start_response,
                    status="400 Bad Request",
                    payload={"error": {"message": str(e)}},
                )
            except (RemoteApiError, ParseError) as e:
                return _json_response(
                    start_response,
                    status="502 Bad Gateway",
                    payload={"error": {"message": str(e)}},
                )
            except Exception:
                traceback.print_exc(file=sys.stderr)
                return _json_response(
                    start_response,
                    status="500 Internal Server Error",
                    payload={
                        "error": {
                            "message": (
                                "Analysis failed unexpectedly. "
                                "Try again in a moment or check the server logs."
                            )
                        }
                    },
                )

        return _json_response(
            start_response,
            status="404 Not Found",
            payload={
                "error": {
                    "message": (
                        "That page was not found. "
                        "Open / in a browser or POST JSON to /api/analyze."
                    )
                }
            },
        )

    return application


app = create_app()


class _QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return None


def run_ui_server(*, host: str = UI_HOST, port: int = UI_PORT) -> None:
    with make_server(host, port, app, handler_class=_QuietRequestHandler) as httpd:
        actual_port = httpd.server_port
        browse_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        print(
            f"Stock Sentiment UI running at http://{browse_host}:{actual_port}"
            f" (bound to {host}:{actual_port})",
            file=sys.stderr,
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return None
