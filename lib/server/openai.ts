/**
 * Per-article sentiment classification via the OpenAI Responses API.
 *
 * Ported from `stock_sentiment/sentiment.py` and `openai_client.py`: one
 * structured-output request classifies every article in the batch, and the
 * response is validated and normalized before it is trusted.
 */

import { ConfigError, UpstreamError } from "./errors";
import type { RawArticle } from "./news";
import type { SentimentLabel } from "@/lib/types";

export interface ArticleSentiment {
  articleId: string;
  label: SentimentLabel;
  score: number;
  confidence: number;
  reason: string | null;
}

export interface ClassificationResult {
  results: ArticleSentiment[];
  warnings: string[];
}

const REQUEST_TIMEOUT_MS = 45_000;
const MAX_ATTEMPTS = 4;
const MAX_OUTPUT_TOKENS = 900;

const SENTIMENT_LABELS: readonly SentimentLabel[] = [
  "positive",
  "negative",
  "neutral",
];

const RESPONSE_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    results: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          article_id: { type: "string" },
          label: { type: "string", enum: ["positive", "negative", "neutral"] },
          score: { type: "number" },
          confidence: { type: "number" },
          reason: { type: "string" },
        },
        required: ["article_id", "label", "score", "confidence", "reason"],
      },
    },
  },
  required: ["results"],
} as const;

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Collapse whitespace and cap length, matching the Python `_truncate`. */
function truncate(text: string, limit: number): string {
  const cleaned = text.split(/\s+/).filter(Boolean).join(" ");
  if (cleaned.length <= limit) return cleaned;
  return `${cleaned.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Best-effort extraction of assistant text from a Responses API payload. */
function extractOutputText(response: unknown): string {
  const payload = response as {
    output_text?: unknown;
    output?: Array<{
      type?: string;
      content?: Array<{ type?: string; text?: unknown }>;
    }>;
  };

  if (typeof payload.output_text === "string" && payload.output_text.trim()) {
    return payload.output_text;
  }

  const chunks: string[] = [];
  for (const item of payload.output ?? []) {
    if (item?.type !== "message") continue;
    for (const content of item.content ?? []) {
      if (content?.type === "output_text" && typeof content.text === "string") {
        chunks.push(content.text);
      }
    }
  }
  return chunks.join("\n").trim();
}

async function callResponsesApi(
  url: string,
  apiKey: string,
  body: unknown,
): Promise<unknown> {
  let lastError = "The model request failed after several retries.";

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
    if (attempt > 0) {
      await sleep(Math.min(8_000, 600 * 2 ** attempt));
    }

    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: {
          authorization: `Bearer ${apiKey}`,
          "content-type": "application/json",
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        cache: "no-store",
      });
    } catch {
      lastError = "The request to the model timed out.";
      continue;
    }

    if (response.ok) {
      return response.json();
    }

    if (response.status === 401 || response.status === 403) {
      throw new ConfigError(
        "The API key was rejected. Check OLLAMA_API_KEY (or OPENAI_API_KEY) in your Vercel project settings.",
      );
    }

    if (response.status === 429 || response.status >= 500) {
      lastError = `The model service is busy (HTTP ${response.status}).`;
      continue;
    }

    throw new UpstreamError(
      `The model request failed (HTTP ${response.status}).`,
    );
  }

  throw new UpstreamError(lastError);
}

export async function classifyArticles(options: {
  ticker: string;
  articles: RawArticle[];
  apiKey: string;
  model: string;
  baseUrl: string;
}): Promise<ClassificationResult> {
  const { ticker, articles, apiKey, model, baseUrl } = options;

  if (articles.length === 0) {
    return { results: [], warnings: [] };
  }
  if (!apiKey) {
    throw new ConfigError(
      "Missing OLLAMA_API_KEY (or OPENAI_API_KEY). Add it to the project's environment variables, then try again.",
    );
  }

  const system =
    "You are a precise financial news sentiment engine. " +
    "Classify each article's expected impact on the stock's price over the next 1-5 trading days. " +
    "Use only the provided text. If unclear, choose neutral. " +
    "Return the requested JSON only.";

  const user = {
    ticker,
    instructions: {
      label: "positive/negative/neutral price impact",
      score: "number in [-1, 1] matching label sign; neutral should be 0",
      confidence: "number in [0, 1]",
      reason: "short justification (<= 20 words)",
    },
    articles: articles.map((article) => ({
      article_id: article.articleId,
      title: truncate(article.title, 220),
      description: truncate(article.description, 900),
      source: article.source,
      published_at: article.publishedAt?.toISOString() ?? null,
    })),
  };

  const body = {
    model,
    input: [
      { role: "system", content: system },
      { role: "user", content: JSON.stringify(user) },
    ],
    text: {
      format: {
        type: "json_schema",
        name: "sentiment_results",
        strict: true,
        schema: RESPONSE_SCHEMA,
      },
    },
    max_output_tokens: MAX_OUTPUT_TOKENS,
  };

  const response = await callResponsesApi(
    `${baseUrl.replace(/\/+$/, "")}/responses`,
    apiKey,
    body,
  );

  const text = extractOutputText(response);
  if (!text) {
    throw new UpstreamError(
      "The model returned an empty response. Try again in a moment.",
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new UpstreamError(
      "The model returned malformed data. Try again in a moment.",
    );
  }

  const rawResults = (parsed as { results?: unknown })?.results;
  if (!Array.isArray(rawResults)) {
    throw new UpstreamError("The model response was missing its results.");
  }

  const requestedIds = new Set(articles.map((article) => article.articleId));
  const byId = new Map<string, ArticleSentiment>();
  let invalidRows = 0;
  let unexpectedResults = 0;
  let duplicateResults = 0;

  for (const row of rawResults) {
    if (!row || typeof row !== "object") {
      invalidRows += 1;
      continue;
    }
    const entry = row as Record<string, unknown>;
    const articleId = entry.article_id;
    const label = entry.label;
    const score = entry.score;
    const confidence = entry.confidence;
    const reason = entry.reason;

    if (typeof articleId !== "string" || !articleId) {
      invalidRows += 1;
      continue;
    }
    if (!requestedIds.has(articleId)) {
      unexpectedResults += 1;
      continue;
    }
    if (byId.has(articleId)) {
      duplicateResults += 1;
      continue;
    }
    if (!SENTIMENT_LABELS.includes(label as SentimentLabel)) {
      invalidRows += 1;
      continue;
    }
    if (!isFiniteNumber(score) || !isFiniteNumber(confidence)) {
      invalidRows += 1;
      continue;
    }

    const normalizedLabel = label as SentimentLabel;
    let normalizedScore = clamp(score, -1, 1);
    if (normalizedLabel === "neutral") {
      normalizedScore = 0;
    } else if (normalizedLabel === "positive") {
      normalizedScore = Math.abs(normalizedScore);
    } else {
      normalizedScore = -Math.abs(normalizedScore);
    }

    byId.set(articleId, {
      articleId,
      label: normalizedLabel,
      score: normalizedScore,
      confidence: clamp(confidence, 0, 1),
      reason:
        typeof reason === "string" && reason.trim()
          ? truncate(reason, 140)
          : null,
    });
  }

  const results: ArticleSentiment[] = [];
  let missingCount = 0;
  for (const article of articles) {
    const existing = byId.get(article.articleId);
    if (existing) {
      results.push(existing);
    } else {
      missingCount += 1;
      results.push({
        articleId: article.articleId,
        label: "neutral",
        score: 0,
        confidence: 0,
        reason: "No classification returned for this article.",
      });
    }
  }

  const warnings: string[] = [];
  if (invalidRows > 0) {
    warnings.push(
      `The model returned ${invalidRows} unreadable classification ${
        invalidRows === 1 ? "row" : "rows"
      }.`,
    );
  }
  if (unexpectedResults > 0) {
    warnings.push(
      `The model returned ${unexpectedResults} classification${
        unexpectedResults === 1 ? "" : "s"
      } for unexpected articles; they were ignored.`,
    );
  }
  if (duplicateResults > 0) {
    warnings.push(
      `The model returned ${duplicateResults} duplicate classification${
        duplicateResults === 1 ? "" : "s"
      }; later duplicates were ignored.`,
    );
  }
  if (missingCount > 0) {
    warnings.push(
      `The model skipped ${missingCount} article${
        missingCount === 1 ? "" : "s"
      }; they were marked neutral with zero confidence.`,
    );
  }

  return { results, warnings };
}
