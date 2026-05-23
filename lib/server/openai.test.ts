import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { ConfigError, UpstreamError } from "./errors";
import { classifyArticles } from "./openai";
import type { RawArticle } from "./news";
import type { Provider } from "./providers";

const ARTICLE: RawArticle = {
  articleId: "a1",
  title: "Headline",
  description: "Body",
  source: "Src",
  url: "https://example.com/a1",
  publishedAt: null,
};

const OK_PAYLOAD = {
  output_text: JSON.stringify({
    results: [
      { article_id: "a1", label: "positive", score: 0.5, confidence: 0.8, reason: "good" },
    ],
  }),
};

const OLLAMA: Provider = {
  name: "ollama",
  apiKey: "k1",
  baseUrl: "https://ollama.com/v1",
  model: "gpt-oss:120b",
};
const OPENROUTER: Provider = {
  name: "openrouter",
  apiKey: "k2",
  baseUrl: "https://openrouter.ai/api/v1",
  model: "openai/gpt-4o-mini",
};

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

/** Replace fetch with a per-host handler and record which hosts were called. */
function stubFetch(handler: (url: string) => Response) {
  const calls: string[] = [];
  globalThis.fetch = (async (input: string | URL | Request) => {
    const url = String(input);
    calls.push(url);
    return handler(url);
  }) as typeof fetch;
  return calls;
}

test("falls over from a rate-limited Ollama to OpenRouter", async () => {
  const calls = stubFetch((url) =>
    url.includes("ollama.com")
      ? new Response("rate limited", { status: 429 })
      : new Response(JSON.stringify(OK_PAYLOAD), { status: 200 }),
  );

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA, OPENROUTER],
  });

  assert.equal(result.results[0].label, "positive");
  assert.ok(calls.some((c) => c.includes("ollama.com")), "tried ollama");
  assert.ok(calls.some((c) => c.includes("openrouter.ai")), "tried openrouter");
});

test("a rejected primary key (401) fails over to the fallback", async () => {
  stubFetch((url) =>
    url.includes("ollama.com")
      ? new Response("unauthorized", { status: 401 })
      : new Response(JSON.stringify(OK_PAYLOAD), { status: 200 }),
  );

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA, OPENROUTER],
  });
  assert.equal(result.results[0].label, "positive");
});

test("400 from the primary is fatal and does not fall over", async () => {
  const calls = stubFetch(() => new Response("bad request", { status: 400 }));

  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, OPENROUTER] }),
    UpstreamError,
  );
  assert.ok(!calls.some((c) => c.includes("openrouter.ai")), "did not try fallback");
});

test("a single rejected key surfaces a ConfigError", async () => {
  stubFetch(() => new Response("unauthorized", { status: 401 }));

  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA] }),
    ConfigError,
  );
});

test("all providers failing surfaces a combined UpstreamError", async () => {
  stubFetch(() => new Response("rate limited", { status: 429 }));

  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, OPENROUTER] }),
    (error: unknown) =>
      error instanceof UpstreamError &&
      error.message.includes("ollama") &&
      error.message.includes("openrouter"),
  );
});

test("an empty provider chain is a ConfigError", async () => {
  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [] }),
    ConfigError,
  );
});
