import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { ConfigError, UpstreamError } from "./errors";
import { __testOnly, classifyArticles } from "./openai";
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

const SECOND_ARTICLE: RawArticle = {
  ...ARTICLE,
  articleId: "a2",
  url: "https://example.com/a2",
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
const GATEWAY: Provider = {
  name: "gateway",
  apiKey: "k2",
  baseUrl: "https://ai-gateway.vercel.sh/v1",
  model: "anthropic/claude-sonnet-5",
};

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

/** Replace fetch with a per-host handler and record which hosts were called. */
function stubFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  const calls: string[] = [];
  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push(url);
    return handler(url, init);
  }) as typeof fetch;
  return calls;
}

function serialTest(name: string, fn: () => void | Promise<void>) {
  return test(name, { concurrency: false }, fn);
}

serialTest("falls over from a rate-limited Ollama to the gateway", async () => {
  const calls = stubFetch((url) =>
    url.includes("ollama.com")
      ? new Response("rate limited", { status: 429 })
      : new Response(JSON.stringify(OK_PAYLOAD), { status: 200 }),
  );

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA, GATEWAY],
  });

  assert.equal(result.results[0].label, "positive");
  assert.equal(result.results[0].classified, true);
  assert.ok(calls.some((c) => c.includes("ollama.com")), "tried ollama");
  assert.ok(calls.some((c) => c.includes("ai-gateway.vercel.sh")), "tried gateway");
});

serialTest("marks synthesized missing rows as unclassified", async () => {
  stubFetch(() => new Response(JSON.stringify(OK_PAYLOAD), { status: 200 }));

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE, SECOND_ARTICLE],
    providers: [OLLAMA],
  });

  assert.equal(result.results[0].classified, true);
  assert.equal(result.results[1].classified, false);
});

serialTest("a rejected primary key (401) fails over to the fallback", async () => {
  stubFetch((url) =>
    url.includes("ollama.com")
      ? new Response("unauthorized", { status: 401 })
      : new Response(JSON.stringify(OK_PAYLOAD), { status: 200 }),
  );

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA, GATEWAY],
  });
  assert.equal(result.results[0].label, "positive");
});

serialTest("a not-found model (404) on the primary fails over to the fallback", async () => {
  const calls = stubFetch((url) =>
    url.includes("ollama.com")
      ? new Response(
          JSON.stringify({ error: { message: 'model "gpt-5.5" not found', type: "not_found_error" } }),
          { status: 404 },
        )
      : new Response(JSON.stringify(OK_PAYLOAD), { status: 200 }),
  );

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA, GATEWAY],
  });

  assert.equal(result.results[0].label, "positive");
  assert.ok(calls.some((c) => c.includes("ollama.com")), "tried ollama");
  assert.ok(calls.some((c) => c.includes("ai-gateway.vercel.sh")), "tried gateway");
});

serialTest("400 from the primary is fatal and does not fall over", async () => {
  const calls = stubFetch(() => new Response("bad request", { status: 400 }));

  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, GATEWAY] }),
    UpstreamError,
  );
  assert.ok(!calls.some((c) => c.includes("ai-gateway.vercel.sh")), "did not try fallback");
});

serialTest("a single rejected key surfaces a ConfigError", async () => {
  stubFetch(() => new Response("unauthorized", { status: 401 }));

  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA] }),
    ConfigError,
  );
});

serialTest("all providers failing surfaces a combined UpstreamError", async () => {
  stubFetch(() => new Response("rate limited", { status: 429 }));

  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, GATEWAY] }),
    (error: unknown) =>
      error instanceof UpstreamError &&
      error.message.includes("ollama") &&
      error.message.includes("gateway"),
  );
});

serialTest("shares the 45-second deadline across fallback provider signals", async () => {
  let now = 1_000_000;
  const timeouts: number[] = [];

  const calls = stubFetch((url, init) => {
    assert.ok(init?.signal instanceof AbortSignal, "request carries an abort signal");
    if (url.includes("ollama.com")) {
      now += 30_000;
      return new Response("rate limited", { status: 429 });
    }
    return new Response(JSON.stringify(OK_PAYLOAD), { status: 200 });
  });

  const result = await __testOnly.classifyArticlesWithDeadline(
    { ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, GATEWAY] },
    {
      now: () => now,
      timeoutSignal: (ms) => {
        timeouts.push(ms);
        return new AbortController().signal;
      },
    },
  );

  assert.equal(result.results[0].classified, true);
  assert.equal(calls.length, 2);
  assert.deepEqual(timeouts, [45_000, 15_000]);
});

serialTest("expires once across retries and fallbacks and maps it to an upstream timeout", async () => {
  let now = 2_000_000;
  const timeouts: number[] = [];

  const calls = stubFetch((url) => {
    assert.ok(url.includes("ollama.com"));
    now += 45_000;
    return new Response("service error", { status: 500 });
  });

  await assert.rejects(
    __testOnly.classifyArticlesWithDeadline(
      { ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, GATEWAY] },
      {
        now: () => now,
        timeoutSignal: (ms) => {
          timeouts.push(ms);
          return new AbortController().signal;
        },
      },
    ),
    (error: unknown) =>
      error instanceof UpstreamError &&
      error.message.includes("ollama: timed out") &&
      error.message.includes("gateway: timed out"),
  );
  assert.equal(calls.length, 1, "does not retry or start a fallback after expiry");
  assert.deepEqual(timeouts, [45_000]);
});

serialTest("body-read aborts retry the provider before using the fallback", async () => {
  let now = 3_000_000;
  const timeouts: number[] = [];

  const calls = stubFetch((url) => {
    if (url.includes("ollama.com")) {
      return new Response(
        new ReadableStream({
          start(controller) {
            controller.error(new DOMException("body aborted", "AbortError"));
          },
        }),
        { status: 200 },
      );
    }
    return new Response(JSON.stringify(OK_PAYLOAD), { status: 200 });
  });

  const result = await __testOnly.classifyArticlesWithDeadline(
    { ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, GATEWAY] },
    {
      now: () => now,
      timeoutSignal: (ms) => {
        timeouts.push(ms);
        return new AbortController().signal;
      },
      sleep: async () => {},
    },
  );

  assert.equal(result.results[0].classified, true);
  assert.deepEqual(
    calls.map((url) => new URL(url).host),
    ["ollama.com", "ollama.com", "ollama.com", "ai-gateway.vercel.sh"],
  );
  assert.deepEqual(timeouts, [45_000, 45_000, 45_000, 45_000]);
});

serialTest("terminated response bodies retry the provider before using the fallback", async () => {
  let now = 3_500_000;
  const timeouts: number[] = [];

  const calls = stubFetch((url) => {
    if (url.includes("ollama.com")) {
      return new Response(
        new ReadableStream({
          start(controller) {
            controller.error(new TypeError("terminated"));
          },
        }),
        { status: 200 },
      );
    }
    return new Response(JSON.stringify(OK_PAYLOAD), { status: 200 });
  });

  const result = await __testOnly.classifyArticlesWithDeadline(
    { ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, GATEWAY] },
    {
      now: () => now,
      timeoutSignal: (ms) => {
        timeouts.push(ms);
        return new AbortController().signal;
      },
      sleep: async () => {},
    },
  );

  assert.equal(result.results[0].classified, true);
  assert.deepEqual(
    calls.map((url) => new URL(url).host),
    ["ollama.com", "ollama.com", "ollama.com", "ai-gateway.vercel.sh"],
  );
  assert.deepEqual(timeouts, [45_000, 45_000, 45_000, 45_000]);
});

serialTest("malformed JSON bodies are not mistaken for transport failures", async () => {
  const calls = stubFetch(() => new Response("{not-json", { status: 200 }));

  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, GATEWAY] }),
    (error: unknown) =>
      error instanceof UpstreamError &&
      error.message.includes("JSON") &&
      !error.message.includes("timed out"),
  );
  assert.equal(calls.length, 1, "does not retry or fall back on malformed JSON");
});

serialTest("a response body completing after the deadline is rejected", async () => {
  let now = 4_000_000;
  const timeouts: number[] = [];

  const calls = stubFetch((url) => {
    assert.ok(url.includes("ollama.com"));
    return new Response(
      new ReadableStream({
        pull(controller) {
          now += 45_000;
          controller.enqueue(new TextEncoder().encode(JSON.stringify(OK_PAYLOAD)));
          controller.close();
        },
      }),
      { status: 200 },
    );
  });

  await assert.rejects(
    __testOnly.classifyArticlesWithDeadline(
      { ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, GATEWAY] },
      {
        now: () => now,
        timeoutSignal: (ms) => {
          timeouts.push(ms);
          return new AbortController().signal;
        },
      },
    ),
    (error: unknown) =>
      error instanceof UpstreamError &&
      error.message.includes("ollama: timed out") &&
      error.message.includes("gateway: timed out"),
  );
  assert.equal(calls.length, 1, "does not fetch a fallback after body overrun");
  assert.deepEqual(timeouts, [45_000]);
});

serialTest("accepts a model that returns an article_id-keyed object (glm shape)", async () => {
  const keyed = {
    a1: { label: "positive", score: 0.6, confidence: 0.8, reason: "beat estimates" },
  };
  stubFetch(() => new Response(JSON.stringify({ output_text: JSON.stringify(keyed) }), { status: 200 }));

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA],
  });
  assert.equal(result.results[0].articleId, "a1");
  assert.equal(result.results[0].label, "positive");
  assert.equal(result.results[0].score, 0.6);
});

serialTest("strips a markdown code fence around the JSON", async () => {
  const fenced =
    "```json\n" +
    JSON.stringify({
      results: [
        { article_id: "a1", label: "negative", score: -0.4, confidence: 0.7, reason: "probe" },
      ],
    }) +
    "\n```";
  stubFetch(() => new Response(JSON.stringify({ output_text: fenced }), { status: 200 }));

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA],
  });
  assert.equal(result.results[0].label, "negative");
});

serialTest("a non-object JSON body is still a missing-results error", async () => {
  stubFetch(() => new Response(JSON.stringify({ output_text: '"just a string"' }), { status: 200 }));

  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA] }),
    (error: unknown) =>
      error instanceof UpstreamError && error.message.includes("missing its results"),
  );
});

serialTest("an empty provider chain is a ConfigError", async () => {
  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [] }),
    ConfigError,
  );
});
