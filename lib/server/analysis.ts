/**
 * Analysis orchestration and aggregation.
 *
 * Ported from `stock_sentiment/runtime.py` and the scoring math in
 * `sentiment.py`: fetch recent news, classify it, then collapse the
 * per-article sentiment into a single score, label, and trading signal.
 */

import { ConfigError } from "./errors";
import { fetchNews, type NewsSource, type RawArticle } from "./news";
import { classifyArticles, type ArticleSentiment } from "./openai";
import type {
  AnalysisArticle,
  AnalysisResult,
  SentimentLabel,
  Signal,
} from "@/lib/types";

const LOOKBACK_DAYS = 3;
const MAX_ARTICLES = 18;
const HALF_LIFE_HOURS = 24;
const SCORE_THRESHOLD = 0.15;
const MIN_SIGNAL_CONFIDENCE = 0.55;

const DEFAULT_MODEL = "gpt-5.4-nano";
const DEFAULT_BASE_URL = "https://api.openai.com/v1";

const SOURCE_LABELS: Record<NewsSource, string> = {
  newsapi: "NewsAPI",
  "google-rss": "Google News RSS",
};

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

export function normalizeTicker(raw: string): string {
  const ticker = raw.trim().toUpperCase();
  if (!ticker) {
    throw new ConfigError("Enter a ticker symbol to begin.");
  }
  if (/\s/.test(ticker)) {
    throw new ConfigError("A ticker cannot contain spaces — try a symbol like TSLA.");
  }
  if (ticker.length > 24) {
    throw new ConfigError("That ticker looks too long — expected a symbol like TSLA.");
  }
  return ticker;
}

/**
 * Exponential time-decay weight: an article loses half its weight every
 * `halfLifeHours`, so fresher coverage dominates the aggregate.
 */
function recencyWeight(
  publishedAt: Date | null,
  halfLifeHours: number,
  now: number,
): number {
  if (!publishedAt) return 1;
  const ageSeconds = Math.max(0, (now - publishedAt.getTime()) / 1000);
  const halfLifeSeconds = Math.max(1, halfLifeHours * 3600);
  return 0.5 ** (ageSeconds / halfLifeSeconds);
}

function labelFromScore(score: number): SentimentLabel {
  if (score > SCORE_THRESHOLD) return "positive";
  if (score < -SCORE_THRESHOLD) return "negative";
  return "neutral";
}

function signalFromScore(score: number, confidence: number): Signal {
  if (confidence < MIN_SIGNAL_CONFIDENCE) return "hold";
  if (score > SCORE_THRESHOLD) return "buy";
  if (score < -SCORE_THRESHOLD) return "sell";
  return "hold";
}

/** Drop duplicate articles (by URL, falling back to id) and cap the count. */
function dedupe(articles: RawArticle[], limit: number): RawArticle[] {
  const seen = new Set<string>();
  const unique: RawArticle[] = [];
  for (const article of articles) {
    const key = article.url ?? article.articleId;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(article);
    if (unique.length >= Math.max(1, limit)) break;
  }
  return unique;
}

export async function analyze(rawTicker: string): Promise<AnalysisResult> {
  const ticker = normalizeTicker(rawTicker);

  const newsApiKey = (process.env.NEWSAPI_KEY ?? "").trim();
  const openAiKey = (
    (process.env.OLLAMA_API_KEY ?? process.env.OPENAI_API_KEY) ?? ""
  ).trim();
  const model = (process.env.OPENAI_MODEL ?? "").trim() || DEFAULT_MODEL;
  const baseUrl = (process.env.OPENAI_BASE_URL ?? "").trim() || DEFAULT_BASE_URL;

  const now = new Date();
  const fromDate = new Date(now.getTime() - LOOKBACK_DAYS * 86_400_000);

  const { source, articles: fetched } = await fetchNews({
    query: ticker,
    fromDate,
    maxArticles: MAX_ARTICLES,
    newsApiKey,
  });
  const articles = dedupe(fetched, MAX_ARTICLES);

  const warnings: string[] = [];
  if (articles.length === 0) {
    warnings.push(
      `No recent headlines were found for ${ticker} in the last ${LOOKBACK_DAYS} days.`,
    );
  }

  const { results, warnings: classificationWarnings } = await classifyArticles({
    ticker,
    articles,
    apiKey: openAiKey,
    model,
    baseUrl,
  });
  warnings.push(...classificationWarnings);

  const summary = summarize({
    ticker,
    source,
    articles,
    results,
    warnings,
    asOf: now,
  });

  const resultsById = new Map(results.map((result) => [result.articleId, result]));
  const articlesPayload: AnalysisArticle[] = articles.map((article) => {
    const sentiment = resultsById.get(article.articleId);
    return {
      article_id: article.articleId,
      title: article.title,
      description: article.description || null,
      url: article.url,
      source: article.source,
      published_at: article.publishedAt?.toISOString() ?? null,
      label: sentiment?.label ?? "neutral",
      score: sentiment?.score ?? 0,
      confidence: sentiment?.confidence ?? 0,
      reason: sentiment?.reason ?? null,
    };
  });

  return { summary, articles: articlesPayload };
}

function summarize(input: {
  ticker: string;
  source: NewsSource;
  articles: RawArticle[];
  results: ArticleSentiment[];
  warnings: string[];
  asOf: Date;
}): AnalysisResult["summary"] {
  const { ticker, source, articles, results, warnings, asOf } = input;
  const now = asOf.getTime();
  const publishedById = new Map(
    articles.map((article) => [article.articleId, article.publishedAt]),
  );

  let totalWeight = 0;
  let totalRecency = 0;
  let weightedScoreSum = 0;

  for (const result of results) {
    const recency = recencyWeight(
      publishedById.get(result.articleId) ?? null,
      HALF_LIFE_HOURS,
      now,
    );
    const weight = recency * clamp(result.confidence, 0, 1);
    totalWeight += weight;
    totalRecency += recency;
    weightedScoreSum += result.score * weight;
  }

  const score = clamp(
    totalWeight > 0 ? weightedScoreSum / totalWeight : 0,
    -1,
    1,
  );
  const confidence = clamp(
    totalRecency > 0 ? totalWeight / totalRecency : 0,
    0,
    1,
  );

  return {
    ticker,
    signal: signalFromScore(score, confidence),
    label: labelFromScore(score),
    score,
    confidence,
    articles_analyzed: results.length,
    classification_degraded: warnings.length > 0,
    classification_warnings: warnings,
    as_of: asOf.toISOString(),
    source,
    source_label: SOURCE_LABELS[source],
    lookback_days: LOOKBACK_DAYS,
    article_cap: MAX_ARTICLES,
  };
}
