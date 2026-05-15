/**
 * News retrieval — Google News RSS (keyless) and NewsAPI (optional key).
 *
 * Ported from the project's Python engine (`stock_sentiment/google_rss.py`,
 * `newsapi.py`, and the `auto` source logic in `runtime.py`).
 */

import { createHash } from "node:crypto";
import { XMLParser } from "fast-xml-parser";
import { UpstreamError } from "./errors";

export type NewsSource = "newsapi" | "google-rss";

export interface RawArticle {
  articleId: string;
  title: string;
  description: string;
  url: string | null;
  source: string | null;
  publishedAt: Date | null;
}

const GOOGLE_TIMEOUT_MS = 20_000;
const NEWSAPI_TIMEOUT_MS = 30_000;

const NAMED_ENTITIES: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&apos;": "'",
  "&#39;": "'",
  "&nbsp;": " ",
};

function decodeEntities(value: string): string {
  return value
    .replace(/&#(\d+);/g, (_, dec: string) =>
      String.fromCodePoint(Number.parseInt(dec, 10)),
    )
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex: string) =>
      String.fromCodePoint(Number.parseInt(hex, 16)),
    )
    .replace(/&[a-zA-Z]+;/g, (entity) => NAMED_ENTITIES[entity] ?? entity);
}

/** Strip markup, decode entities, and collapse whitespace. */
function cleanText(value: string): string {
  return decodeEntities(value.replace(/<[^>]+>/g, " "))
    .replace(/\s+/g, " ")
    .trim();
}

function stableArticleId(...parts: Array<string | null | undefined>): string {
  const joined = parts
    .filter((part): part is string => typeof part === "string" && part.length > 0)
    .map((part) => part.trim())
    .join("|");
  return createHash("sha256").update(joined, "utf8").digest("hex").slice(0, 16);
}

/** Parse RFC 2822 (RSS) or ISO 8601 (NewsAPI) timestamps; null when unparseable. */
function parseDate(value: unknown): Date | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = new Date(value.trim());
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

async function fetchText(
  url: string,
  init: RequestInit,
  label: string,
): Promise<string> {
  let response: Response;
  try {
    response = await fetch(url, { ...init, cache: "no-store" });
  } catch {
    throw new UpstreamError(
      `${label} could not be reached. Check the connection and try again.`,
    );
  }
  if (!response.ok) {
    throw new UpstreamError(`${label} responded with HTTP ${response.status}.`);
  }
  return response.text();
}

export async function fetchGoogleNewsRss(
  query: string,
  fromDate: Date,
): Promise<RawArticle[]> {
  const params = new URLSearchParams({
    q: query,
    hl: "en-US",
    gl: "US",
    ceid: "US:en",
  });
  const xml = await fetchText(
    `https://news.google.com/rss/search?${params.toString()}`,
    {
      headers: {
        "user-agent": "Mozilla/5.0 (compatible; StockSentiment/1.0)",
      },
      signal: AbortSignal.timeout(GOOGLE_TIMEOUT_MS),
    },
    "Google News",
  );

  let parsed: unknown;
  try {
    parsed = new XMLParser({
      ignoreAttributes: false,
      attributeNamePrefix: "@_",
      textNodeName: "#text",
    }).parse(xml);
  } catch {
    throw new UpstreamError("Google News returned data that could not be read.");
  }

  const channel = (parsed as { rss?: { channel?: { item?: unknown } } })?.rss
    ?.channel;
  const rawItems = channel?.item;
  const items = Array.isArray(rawItems) ? rawItems : rawItems ? [rawItems] : [];

  const articles: RawArticle[] = [];
  for (const entry of items as Array<Record<string, unknown>>) {
    const title = String(entry?.title ?? "").trim();
    const link = String(entry?.link ?? "").trim() || null;
    const description = cleanText(String(entry?.description ?? ""));

    let source: string | null = null;
    const rawSource = entry?.source;
    if (typeof rawSource === "string") {
      source = rawSource.trim() || null;
    } else if (rawSource && typeof rawSource === "object") {
      source =
        String((rawSource as Record<string, unknown>)["#text"] ?? "").trim() ||
        null;
    }

    const publishedAt = parseDate(entry?.pubDate);
    if (publishedAt && publishedAt < fromDate) continue;
    if (!title && !description) continue;

    articles.push({
      articleId: stableArticleId(
        link ?? "",
        title,
        publishedAt?.toISOString() ?? "",
      ),
      title,
      description,
      url: link,
      source,
      publishedAt,
    });
  }
  return articles;
}

export async function fetchNewsApi(
  apiKey: string,
  query: string,
  fromDate: Date,
  limit: number,
): Promise<RawArticle[]> {
  const params = new URLSearchParams({
    q: query,
    language: "en",
    sortBy: "publishedAt",
    pageSize: String(Math.min(100, Math.max(1, limit))),
    page: "1",
    from: fromDate.toISOString().slice(0, 10),
  });

  const body = await fetchText(
    `https://newsapi.org/v2/everything?${params.toString()}`,
    {
      headers: { "x-api-key": apiKey },
      signal: AbortSignal.timeout(NEWSAPI_TIMEOUT_MS),
    },
    "NewsAPI",
  );

  let data: unknown;
  try {
    data = JSON.parse(body);
  } catch {
    throw new UpstreamError("NewsAPI returned data that could not be read.");
  }

  const rawArticles = (data as { articles?: unknown })?.articles;
  const items = Array.isArray(rawArticles) ? rawArticles : [];

  const articles: RawArticle[] = [];
  for (const entry of items as Array<Record<string, unknown>>) {
    const title = String(entry?.title ?? "").trim();
    const description = String(entry?.description ?? "").trim();
    const rawUrl = entry?.url;
    const url =
      typeof rawUrl === "string" && rawUrl.trim() ? rawUrl.trim() : null;
    const sourceName = (entry?.source as Record<string, unknown> | undefined)
      ?.name;
    const source =
      typeof sourceName === "string" ? sourceName.trim() || null : null;
    const publishedAt = parseDate(entry?.publishedAt);

    if (!title && !description) continue;

    articles.push({
      articleId: stableArticleId(
        url ?? "",
        title,
        publishedAt?.toISOString() ?? "",
      ),
      title,
      description,
      url,
      source,
      publishedAt,
    });
  }
  return articles;
}

/**
 * `auto` source selection: prefer NewsAPI when a key is configured, and fall
 * back to keyless Google News RSS if NewsAPI is unavailable.
 */
export async function fetchNews(options: {
  query: string;
  fromDate: Date;
  maxArticles: number;
  newsApiKey: string;
}): Promise<{ source: NewsSource; articles: RawArticle[] }> {
  const { query, fromDate, maxArticles, newsApiKey } = options;

  if (newsApiKey) {
    try {
      const articles = await fetchNewsApi(
        newsApiKey,
        query,
        fromDate,
        Math.max(1, maxArticles),
      );
      return { source: "newsapi", articles };
    } catch {
      // Fall through to the keyless Google News RSS source.
    }
  }

  const articles = await fetchGoogleNewsRss(query, fromDate);
  return { source: "google-rss", articles };
}
