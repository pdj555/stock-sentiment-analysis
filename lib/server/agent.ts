/**
 * Per-article sentiment classification via the OpenAI Agents SDK, running on
 * Ollama Cloud (its OpenAI-compatible Chat Completions API).
 *
 * Replaces the hand-rolled Responses-API client: a single sentiment Agent
 * classifies the whole batch in one turn. We do not rely on the SDK's
 * `outputType` because Ollama Cloud does not strictly enforce the json_schema
 * response format for thinking models (they wrap the JSON in reasoning/prose),
 * so the reply is parsed defensively (`extractJson`) and then normalized
 * (label→score sign, neutral→0, dedup, missing-fill) before it is trusted.
 *
 * Provider: Ollama Cloud. Point it elsewhere (any OpenAI-compatible endpoint)
 * with OLLAMA_BASE_URL / OLLAMA_MODEL; OLLAMA_API_KEY is required.
 */

import {
  Agent,
  run,
  setDefaultOpenAIClient,
  setOpenAIAPI,
  setTracingDisabled,
} from "@openai/agents";
import OpenAI from "openai";
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

/** Ollama Cloud's OpenAI-compatible endpoint (note: no `api.` subdomain). */
const DEFAULT_BASE_URL = "https://ollama.com/v1";
/** General-purpose, tool-capable default; OLLAMA_MODEL overrides it. */
const DEFAULT_MODEL = "kimi-k2.6:cloud";
const MAX_OUTPUT_TOKENS = 3200;

const SENTIMENT_LABELS: readonly SentimentLabel[] = [
  "positive",
  "negative",
  "neutral",
];

const SYSTEM_PROMPT = [
  "You are a precise financial news sentiment engine.",
  "Classify each article's expected impact on the stock's price over the next 1-5 trading days.",
  "Use only the provided text. If unclear, choose neutral.",
  "",
  "Return ONLY a JSON object (no markdown, no code fences, no commentary) of the form:",
  '{"results":[{"article_id":string,"label":"positive"|"negative"|"neutral","score":number,"confidence":number,"reason":string}]}',
  "Rules: one result per input article, echoing its article_id exactly;",
  "score is in [-1,1] matching the label sign (neutral is 0); confidence is in [0,1];",
  "reason is a short justification (<= 20 words).",
].join("\n");

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Collapse whitespace and cap length, matching the Python `_truncate`. */
function truncate(text: string, limit: number): string {
  const cleaned = text.split(/\s+/).filter(Boolean).join(" ");
  if (cleaned.length <= limit) return cleaned;
  return `${cleaned.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

/**
 * Pull the JSON object out of a model reply that may wrap it in `<think>`
 * reasoning, markdown fences, or surrounding prose. Returns `null` when
 * nothing parseable is found.
 */
export function extractJson(text: string): unknown {
  if (!text) return null;
  const cleaned = text
    .replace(/<think>[\s\S]*?<\/think>/gi, "") // drop reasoning blocks
    .replace(/```[a-zA-Z]*/g, "") // drop code-fence markers
    .trim();

  try {
    return JSON.parse(cleaned);
  } catch {
    // Fall back to the outermost {...} span (handles leading/trailing prose).
    const start = cleaned.indexOf("{");
    const end = cleaned.lastIndexOf("}");
    if (start === -1 || end <= start) return null;
    try {
      return JSON.parse(cleaned.slice(start, end + 1));
    } catch {
      return null;
    }
  }
}

/** Resolve Ollama Cloud connection details from the environment. */
function resolveOllamaConfig(): { apiKey: string; baseURL: string; model: string } {
  const apiKey = process.env.OLLAMA_API_KEY?.trim();
  if (!apiKey) {
    throw new ConfigError(
      "Missing OLLAMA_API_KEY. Add your Ollama Cloud key to the project's environment variables, then try again.",
    );
  }
  return {
    apiKey,
    baseURL:
      process.env.OLLAMA_BASE_URL?.trim() ||
      process.env.OPENAI_BASE_URL?.trim() ||
      DEFAULT_BASE_URL,
    model:
      process.env.OLLAMA_MODEL?.trim() ||
      process.env.OPENAI_MODEL?.trim() ||
      DEFAULT_MODEL,
  };
}

let configuredKey: string | null = null;

/**
 * Point the Agents SDK at Ollama Cloud. The SDK keeps a single default client,
 * so we (re)configure only when the resolved key changes. Tracing is disabled
 * because the SDK's tracer exports to OpenAI's backend, which we do not use.
 */
function configureProvider(apiKey: string, baseURL: string): void {
  const fingerprint = `${baseURL}::${apiKey}`;
  if (configuredKey === fingerprint) return;
  setDefaultOpenAIClient(new OpenAI({ apiKey, baseURL }));
  setOpenAIAPI("chat_completions");
  setTracingDisabled(true);
  configuredKey = fingerprint;
}

/**
 * Normalize the model's parsed rows into trusted `ArticleSentiment`s: keep only
 * requested ids, dedupe, coerce score to the label's sign (neutral → 0), and
 * backfill any skipped article as neutral/zero. Returns the per-article results
 * plus human-readable warnings about anything dropped.
 */
export function normalizeClassification(
  rawResults: ReadonlyArray<unknown>,
  articles: RawArticle[],
): ClassificationResult {
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

/** Build the single user message: the ticker plus the batch to classify. */
function buildInput(ticker: string, articles: RawArticle[]): string {
  return JSON.stringify({
    ticker,
    articles: articles.map((article) => ({
      article_id: article.articleId,
      title: truncate(article.title, 220),
      description: truncate(article.description, 900),
      source: article.source,
      published_at: article.publishedAt?.toISOString() ?? null,
    })),
  });
}

/**
 * Classify a batch of articles with a sentiment Agent on Ollama Cloud.
 * Throws `ConfigError` when the provider key is missing and `UpstreamError`
 * when the model call fails or returns nothing usable.
 */
export async function classifyArticles(options: {
  ticker: string;
  articles: RawArticle[];
}): Promise<ClassificationResult> {
  const { ticker, articles } = options;

  if (articles.length === 0) {
    return { results: [], warnings: [] };
  }

  const { apiKey, baseURL, model } = resolveOllamaConfig();
  configureProvider(apiKey, baseURL);

  const agent = new Agent({
    name: "Stock sentiment classifier",
    instructions: SYSTEM_PROMPT,
    model,
    modelSettings: { maxTokens: MAX_OUTPUT_TOKENS },
  });

  let text = "";
  try {
    const result = await run(agent, buildInput(ticker, articles), {
      maxTurns: 1,
    });
    text = typeof result.finalOutput === "string" ? result.finalOutput : "";
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (/401|403|unauthor|api key|invalid_api_key/i.test(message)) {
      throw new ConfigError(
        "The Ollama API key was rejected. Check OLLAMA_API_KEY in your project settings.",
      );
    }
    throw new UpstreamError(`The AI request failed — ${message}.`);
  }

  const parsed = extractJson(text);
  const rows = (parsed as { results?: unknown } | null)?.results;
  if (!Array.isArray(rows)) {
    throw new UpstreamError(
      "The model returned an empty or malformed response. Try again in a moment.",
    );
  }

  return normalizeClassification(rows, articles);
}
