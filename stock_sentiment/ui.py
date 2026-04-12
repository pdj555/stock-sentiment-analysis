from __future__ import annotations

import json
import os
import sys
import traceback
from collections.abc import Callable, Iterable
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
    <title>Stock Sentiment</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f4f6f5;
        --bg-overlay: rgba(244, 246, 245, 0.78);
        --line: rgba(10, 12, 11, 0.12);
        --text: #0f1210;
        --muted: #5c655f;
        --positive: #175f49;
        --negative: #8a342e;
        --neutral: #6c5d1c;
      }

      * {
        box-sizing: border-box;
      }

      html,
      body {
        margin: 0;
        min-height: 100%;
        background: var(--bg);
        color: var(--text);
        font-family: Inter, "Segoe UI", Helvetica, Arial, sans-serif;
        letter-spacing: 0;
      }

      body::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -2;
        background: url("https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1800&q=80")
          68% center / cover no-repeat;
        opacity: 0.28;
        filter: saturate(0.92) contrast(1.08);
        transform: scale(1.02);
      }

      body::after {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -1;
        background: var(--bg-overlay);
        backdrop-filter: blur(3px);
      }

      a {
        color: inherit;
      }

      main {
        max-width: 940px;
        margin: 0 auto;
        padding: 28px 20px 56px;
      }

      .topline {
        display: grid;
        gap: 10px;
        padding-bottom: 22px;
        border-bottom: 1px solid var(--line);
      }

      .brand {
        font-size: 14px;
        font-weight: 700;
      }

      h1 {
        margin: 0;
        max-width: 11ch;
        font-size: 36px;
        line-height: 1.02;
        font-weight: 700;
      }

      .form-row {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 10px;
        align-items: end;
        margin-top: 28px;
      }

      label {
        display: block;
        margin-bottom: 8px;
        font-size: 13px;
        color: var(--muted);
      }

      input {
        width: 100%;
        height: 56px;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0 16px;
        background: rgba(255, 255, 255, 0.72);
        color: var(--text);
        font-size: 24px;
        font-weight: 600;
        text-transform: uppercase;
        outline: none;
        transition: border-color 0.16s ease, background-color 0.16s ease;
      }

      input:focus {
        border-color: rgba(10, 12, 11, 0.3);
        background: rgba(255, 255, 255, 0.9);
      }

      button {
        height: 56px;
        min-width: 128px;
        border: 0;
        border-radius: 8px;
        padding: 0 20px;
        background: var(--text);
        color: #f8faf8;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.16s ease, opacity 0.16s ease;
      }

      button:hover {
        transform: translateY(-1px);
      }

      button:disabled {
        opacity: 0.68;
        cursor: wait;
        transform: none;
      }

      .status-line {
        min-height: 22px;
        margin: 12px 0 0;
        color: var(--muted);
        font-size: 14px;
      }

      .results {
        margin-top: 28px;
        border-top: 1px solid var(--line);
      }

      .state {
        display: flex;
        align-items: center;
        min-height: 96px;
        color: var(--muted);
        font-size: 15px;
      }

      .state.error {
        color: var(--negative);
      }

      .summary-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 18px;
        padding: 20px 0;
        border-bottom: 1px solid var(--line);
        animation: rise 0.24s ease;
      }

      .summary-warning {
        margin: 14px 0 0;
        font-size: 14px;
        line-height: 1.4;
        color: var(--negative);
      }

      .metric {
        min-width: 0;
      }

      .metric dt {
        margin: 0;
        font-size: 12px;
        color: var(--muted);
        text-transform: uppercase;
      }

      .metric dd {
        margin: 6px 0 0;
        font-size: 22px;
        font-weight: 700;
        line-height: 1.1;
      }

      .articles {
        list-style: none;
        margin: 0;
        padding: 0;
      }

      .article {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 18px;
        padding: 18px 0;
        border-bottom: 1px solid var(--line);
        animation: rise 0.24s ease;
      }

      .article-title {
        margin: 0;
        font-size: 19px;
        line-height: 1.28;
        font-weight: 600;
      }

      .article-title a {
        text-decoration: none;
      }

      .article-title a:hover {
        text-decoration: underline;
      }

      .article-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 14px;
        margin-top: 8px;
        color: var(--muted);
        font-size: 13px;
      }

      .article-reason {
        max-width: 64ch;
        margin-top: 10px;
        font-size: 15px;
        line-height: 1.45;
      }

      .badge {
        align-self: start;
        border-radius: 999px;
        padding: 6px 9px;
        font-size: 12px;
        font-weight: 700;
        background: rgba(10, 12, 11, 0.06);
        color: var(--text);
      }

      .badge.positive {
        background: rgba(23, 95, 73, 0.12);
        color: var(--positive);
      }

      .badge.negative {
        background: rgba(138, 52, 46, 0.12);
        color: var(--negative);
      }

      .badge.neutral {
        background: rgba(108, 93, 28, 0.12);
        color: var(--neutral);
      }

      .footer {
        margin-top: 26px;
        color: var(--muted);
        font-size: 13px;
      }

      @keyframes rise {
        from {
          opacity: 0;
          transform: translateY(8px);
        }

        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      @media (max-width: 820px) {
        h1 {
          font-size: 30px;
        }

        .summary-grid {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
      }

      @media (max-width: 680px) {
        main {
          padding: 22px 16px 44px;
        }

        .form-row,
        .article {
          grid-template-columns: minmax(0, 1fr);
        }

        button {
          width: 100%;
        }

        .summary-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }

      @media (max-width: 460px) {
        h1 {
          font-size: 26px;
        }

        input {
          font-size: 20px;
        }

        .metric dd {
          font-size: 18px;
        }

        .article-title {
          font-size: 17px;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <header class="topline">
        <div class="brand">Stock Sentiment</div>
        <h1>Recent news in one read.</h1>
      </header>

      <form id="analyze-form" class="form-row">
        <div>
          <label for="ticker">Ticker</label>
          <input
            id="ticker"
            name="ticker"
            placeholder="TSLA"
            autocomplete="off"
            autocapitalize="characters"
            spellcheck="false"
            maxlength="24"
          >
        </div>
        <button id="submit-button" type="submit">Analyze</button>
      </form>

      <p id="status-line" class="status-line"></p>

      <section class="results" aria-live="polite">
        <div id="summary" class="state">Start with a ticker.</div>
        <ul id="articles" class="articles"></ul>
      </section>

      <p class="footer">Not financial advice.</p>
    </main>

    <script>
      const form = document.getElementById("analyze-form");
      const tickerInput = document.getElementById("ticker");
      const submitButton = document.getElementById("submit-button");
      const statusLine = document.getElementById("status-line");
      const summary = document.getElementById("summary");
      const articles = document.getElementById("articles");

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
        statusLine.textContent = `Analyzing ${ticker}...`;

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
          statusLine.textContent = asOf
            ? `${sourceLabel} - ${windowDays}-day lookback${coverage} - as of ${asOf}`
            : `${sourceLabel} - ${windowDays}-day lookback${coverage}`;
        } catch (error) {
          const message = error && error.message
            ? error.message
            : "The analysis could not load. Check your connection or restart the server, then try again.";
          renderError(message);
          statusLine.textContent = message;
        } finally {
          submitButton.disabled = false;
        }
      }

      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const ticker = tickerInput.value.trim().toUpperCase();
        if (!ticker) {
          renderError("Ticker cannot be empty.");
          statusLine.textContent = "Enter a ticker.";
          tickerInput.focus();
          return;
        }

        analyzeTicker(ticker);
      });

      tickerInput.addEventListener("input", () => {
        if (summary.classList.contains("error")) {
          renderIdle("Start with a ticker.");
          statusLine.textContent = "";
        }
      });
    </script>
  </body>
</html>
"""


def _display_source_name(source: str) -> str:
    return display_source_name(source)


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
                cache_dir=default_cache_dir(),
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
        raise ConfigurationError("Request body must be valid JSON.") from e

    if not isinstance(parsed, dict):
        raise ConfigurationError("Request body must be a JSON object.")
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
                    raise ConfigurationError("Ticker must be a string.")
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
