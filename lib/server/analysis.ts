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
import { resolveProviders } from "./providers";
import type {
  AnalysisArticle,
  AnalysisResult,
  EvidenceDriver,
  EvidenceGrade,
  EvidenceProfile,
  SentimentLabel,
  Signal,
} from "@/lib/types";

const LOOKBACK_DAYS = 3;
const MAX_ARTICLES = 18;
const HALF_LIFE_HOURS = 24;
const SCORE_THRESHOLD = 0.15;
const MIN_SIGNAL_CONFIDENCE = 0.55;
const MIN_SIGNAL_AGREEMENT = 0.55;
const MIN_CLASSIFIED_ARTICLES = 3;
const MIN_EVIDENCE_COVERAGE = 0.6;
const STRONG_CLASSIFIED_ARTICLES = 5;
const STRONG_EVIDENCE_COVERAGE = 0.8;
const STRONG_EVIDENCE_AGREEMENT = 0.7;
const STRONG_EVIDENCE_CONFIDENCE = 0.65;

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

function signalFromScore(
  score: number,
  confidence: number,
  grade: EvidenceGrade,
  agreement: number,
): Signal {
  if (grade === "limited") return "hold";
  if (confidence < MIN_SIGNAL_CONFIDENCE) return "hold";
  if (agreement < MIN_SIGNAL_AGREEMENT) return "hold";
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

  const env = (name: string) => (process.env[name] ?? "").trim();
  const newsApiKey = env("NEWSAPI_KEY");
  const providers = resolveProviders(env).filter((provider) => provider.model);

  if (providers.length === 0) {
    throw new ConfigError(
      "Missing AI provider config. Set AI_MODEL plus a key for its route (OLLAMA_API_KEY for a bare model id, AI_GATEWAY_API_KEY or VERCEL_OIDC_TOKEN for a provider/model id), then try again.",
    );
  }

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
    providers,
  });
  warnings.push(...classificationWarnings);

  const { summary, evidence } = summarizeAnalysis({
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
      classified: sentiment?.classified ?? false,
    };
  });

  return { summary, evidence, articles: articlesPayload };
}

export function summarizeAnalysis(input: {
  ticker: string;
  source: NewsSource;
  articles: RawArticle[];
  results: ArticleSentiment[];
  warnings: string[];
  asOf: Date;
}): Pick<AnalysisResult, "summary" | "evidence"> {
  const { ticker, source, articles, results, warnings, asOf } = input;
  const now = asOf.getTime();
  const articlesById = new Map(articles.map((article) => [article.articleId, article]));

  let totalWeight = 0;
  let totalRecency = 0;
  let weightedScoreSum = 0;
  let directionalImpact = 0;
  let absoluteDirectionalImpact = 0;
  const candidates: EvidenceDriver[] = [];

  for (const result of results) {
    const article = articlesById.get(result.articleId);
    const recency = recencyWeight(
      article?.publishedAt ?? null,
      HALF_LIFE_HOURS,
      now,
    );
    const confidence = clamp(result.confidence, 0, 1);
    const weight = recency * confidence;
    const impact = result.score * weight;
    totalWeight += weight;
    totalRecency += recency;
    weightedScoreSum += impact;
    directionalImpact += impact;
    absoluteDirectionalImpact += Math.abs(impact);

    if (result.classified && result.label !== "neutral" && article) {
      candidates.push({
        article_id: article.articleId,
        title: article.title,
        url: article.url,
        source: article.source,
        published_at: article.publishedAt?.toISOString() ?? null,
        direction: impact >= 0 ? "positive" : "negative",
        impact,
        confidence,
        reason: result.reason,
      });
    }
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
  const classifiedArticles = results.filter((result) => result.classified).length;
  const totalArticles = articles.length;
  const coverage = totalArticles > 0 ? classifiedArticles / totalArticles : 0;
  const agreement =
    absoluteDirectionalImpact > 0
      ? Math.abs(directionalImpact) / absoluteDirectionalImpact
      : 0;
  const grade: EvidenceGrade =
    classifiedArticles < MIN_CLASSIFIED_ARTICLES || coverage < MIN_EVIDENCE_COVERAGE
      ? "limited"
      : classifiedArticles >= STRONG_CLASSIFIED_ARTICLES &&
          coverage >= STRONG_EVIDENCE_COVERAGE &&
          agreement >= STRONG_EVIDENCE_AGREEMENT &&
          confidence >= STRONG_EVIDENCE_CONFIDENCE
        ? "strong"
        : "moderate";

  const ranked = candidates.sort(
    (left, right) =>
      Math.abs(right.impact) - Math.abs(left.impact) ||
      left.article_id.localeCompare(right.article_id),
  );
  const drivers: EvidenceDriver[] = [];
  const selectedIds = new Set<string>();
  const addDriver = (driver: EvidenceDriver | undefined) => {
    if (!driver || selectedIds.has(driver.article_id) || drivers.length >= 3) return;
    selectedIds.add(driver.article_id);
    drivers.push(driver);
  };

  const strongest = ranked[0];
  addDriver(strongest);
  if (strongest) {
    addDriver(ranked.find((driver) => driver.direction !== strongest.direction));
  }
  for (const driver of ranked) {
    addDriver(driver);
  }

  const evidence: EvidenceProfile = {
    grade,
    coverage,
    agreement,
    classified_articles: classifiedArticles,
    total_articles: totalArticles,
    drivers,
  };

  const summary = {
    ticker,
    signal: signalFromScore(score, confidence, grade, agreement),
    label: labelFromScore(score),
    score,
    confidence,
    articles_analyzed: classifiedArticles,
    classification_degraded: warnings.length > 0,
    classification_warnings: warnings,
    as_of: asOf.toISOString(),
    source,
    source_label: SOURCE_LABELS[source],
    lookback_days: LOOKBACK_DAYS,
    article_cap: MAX_ARTICLES,
  };

  return { summary, evidence };
}
