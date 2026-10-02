import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { addTraceProcessor } from "@openai/agents";

import { analyze } from "./analysis";

import { ConfigError, UpstreamError } from "./errors";
import { __testOnly, classifyArticles } from "./agent";
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

const OK_TEXT = JSON.stringify({
  results: [
    {
      article_id: "a1",
      label: "positive",
      score: 0.5,
      confidence: 0.8,
      reason: "good",
    },
  ],
});

function payload(text: string, gateway = false) {
  return gateway
    ? {
        id: "resp_test",
        object: "response",
        status: "completed",
        output: [
          {
            id: "msg_test",
            type: "message",
            status: "completed",
            role: "assistant",
            content: [{ type: "output_text", text, annotations: [] }],
          },
        ],
      }
    : {
        id: "chat_test",
        object: "chat.completion",
        choices: [
          {
            index: 0,
            finish_reason: "stop",
            message: { role: "assistant", content: text },
          },
        ],
      };
}

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
function stubFetch(
  handler: (url: string, init?: RequestInit) => Response | Promise<Response>,
) {
  const calls: string[] = [];
  globalThis.fetch = (async (
    input: string | URL | Request,
    init?: RequestInit,
  ) => {
    const url = String(input);
    calls.push(url);
    const response = await handler(url, init);
    response.headers.set("content-type", "application/json");
    return response;
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
      : new Response(
          JSON.stringify(payload(OK_TEXT, url.includes("ai-gateway"))),
          { status: 200 },
        ),
  );

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA, GATEWAY],
  });

  assert.equal(result.results[0].label, "positive");
  assert.equal(result.results[0].classified, true);
  assert.ok(
    calls.some((c) => c.includes("ollama.com")),
    "tried ollama",
  );
  assert.ok(
    calls.some((c) => c.includes("ai-gateway.vercel.sh")),
    "tried gateway",
  );
});

serialTest("marks synthesized missing rows as unclassified", async () => {
  stubFetch(
    (url) =>
      new Response(
        JSON.stringify(payload(OK_TEXT, url.includes("ai-gateway"))),
        { status: 200 },
      ),
  );

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE, SECOND_ARTICLE],
    providers: [OLLAMA],
  });

  assert.equal(result.results[0].classified, true);
  assert.equal(result.results[1].classified, false);
});

serialTest(
  "a rejected primary key (401) fails over to the fallback",
  async () => {
    stubFetch((url) =>
      url.includes("ollama.com")
        ? new Response("unauthorized", { status: 401 })
        : new Response(
            JSON.stringify(payload(OK_TEXT, url.includes("ai-gateway"))),
            { status: 200 },
          ),
    );

    const result = await classifyArticles({
      ticker: "TSLA",
      articles: [ARTICLE],
      providers: [OLLAMA, GATEWAY],
    });
    assert.equal(result.results[0].label, "positive");
  },
);

serialTest(
  "a not-found model (404) on the primary fails over to the fallback",
  async () => {
    const calls = stubFetch((url) =>
      url.includes("ollama.com")
        ? new Response(
            JSON.stringify({
              error: {
                message: 'model "gpt-5.5" not found',
                type: "not_found_error",
              },
            }),
            { status: 404 },
          )
        : new Response(
            JSON.stringify(payload(OK_TEXT, url.includes("ai-gateway"))),
            { status: 200 },
          ),
    );

    const result = await classifyArticles({
      ticker: "TSLA",
      articles: [ARTICLE],
      providers: [OLLAMA, GATEWAY],
    });

    assert.equal(result.results[0].label, "positive");
    assert.ok(
      calls.some((c) => c.includes("ollama.com")),
      "tried ollama",
    );
    assert.ok(
      calls.some((c) => c.includes("ai-gateway.vercel.sh")),
      "tried gateway",
    );
  },
);

serialTest("400 from the primary is fatal and does not fall over", async () => {
  const calls = stubFetch(() => new Response("bad request", { status: 400 }));

  await assert.rejects(
    classifyArticles({
      ticker: "TSLA",
      articles: [ARTICLE],
      providers: [OLLAMA, GATEWAY],
    }),
    UpstreamError,
  );
  assert.ok(
    !calls.some((c) => c.includes("ai-gateway.vercel.sh")),
    "did not try fallback",
  );
});

serialTest("a single rejected key surfaces a ConfigError", async () => {
  stubFetch(() => new Response("unauthorized", { status: 401 }));

  await assert.rejects(
    classifyArticles({
      ticker: "TSLA",
      articles: [ARTICLE],
      providers: [OLLAMA],
    }),
    ConfigError,
  );
});

serialTest(
  "all providers failing surfaces a combined UpstreamError",
  async () => {
    stubFetch(() => new Response("rate limited", { status: 429 }));

    await assert.rejects(
      classifyArticles({
        ticker: "TSLA",
        articles: [ARTICLE],
        providers: [OLLAMA, GATEWAY],
      }),
      (error: unknown) =>
        error instanceof UpstreamError &&
        error.message.includes("ollama") &&
        error.message.includes("gateway"),
    );
  },
);

serialTest(
  "shares the 45-second deadline across fallback provider signals",
  async () => {
    let now = 1_000_000;
    const timeouts: number[] = [];

    const calls = stubFetch((url, init) => {
      assert.ok(
        init?.signal instanceof AbortSignal,
        "request carries an abort signal",
      );
      if (url.includes("ollama.com")) {
        now += 30_000;
        return new Response("rate limited", { status: 429 });
      }
      return new Response(
        JSON.stringify(payload(OK_TEXT, url.includes("ai-gateway"))),
        { status: 200 },
      );
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
  },
);

serialTest(
  "expires once across retries and fallbacks and maps it to an upstream timeout",
  async () => {
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
    assert.equal(
      calls.length,
      1,
      "does not retry or start a fallback after expiry",
    );
    assert.deepEqual(timeouts, [45_000]);
  },
);

serialTest(
  "body-read aborts retry the provider before using the fallback",
  async () => {
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
      return new Response(
        JSON.stringify(payload(OK_TEXT, url.includes("ai-gateway"))),
        { status: 200 },
      );
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
  },
);

serialTest(
  "terminated response bodies retry the provider before using the fallback",
  async () => {
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
      return new Response(
        JSON.stringify(payload(OK_TEXT, url.includes("ai-gateway"))),
        { status: 200 },
      );
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
  },
);

serialTest(
  "malformed JSON bodies are not mistaken for transport failures",
  async () => {
    const calls = stubFetch(() => new Response("{not-json", { status: 200 }));

    await assert.rejects(
      classifyArticles({
        ticker: "TSLA",
        articles: [ARTICLE],
        providers: [OLLAMA, GATEWAY],
      }),
      (error: unknown) =>
        error instanceof UpstreamError &&
        error.message.includes("JSON") &&
        !error.message.includes("timed out"),
    );
    assert.equal(
      calls.length,
      1,
      "does not retry or fall back on malformed JSON",
    );
  },
);

serialTest(
  "a response body completing after the deadline is rejected",
  async () => {
    let now = 4_000_000;
    const timeouts: number[] = [];

    const calls = stubFetch((url) => {
      assert.ok(url.includes("ollama.com"));
      return new Response(
        new ReadableStream({
          pull(controller) {
            now += 45_000;
            controller.enqueue(
              new TextEncoder().encode(
                JSON.stringify(payload(OK_TEXT, url.includes("ai-gateway"))),
              ),
            );
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
    assert.equal(
      calls.length,
      1,
      "does not fetch a fallback after body overrun",
    );
    assert.deepEqual(timeouts, [45_000]);
  },
);

serialTest(
  "accepts a model that returns an article_id-keyed object (glm shape)",
  async () => {
    const keyed = {
      a1: {
        label: "positive",
        score: 0.6,
        confidence: 0.8,
        reason: "beat estimates",
      },
    };
    stubFetch(
      () =>
        new Response(JSON.stringify(payload(JSON.stringify(keyed))), {
          status: 200,
        }),
    );

    const result = await classifyArticles({
      ticker: "TSLA",
      articles: [ARTICLE],
      providers: [OLLAMA],
    });
    assert.equal(result.results[0].articleId, "a1");
    assert.equal(result.results[0].label, "positive");
    assert.equal(result.results[0].score, 0.6);
  },
);

serialTest("strips a markdown code fence around the JSON", async () => {
  const fenced =
    "```json\n" +
    JSON.stringify({
      results: [
        {
          article_id: "a1",
          label: "negative",
          score: -0.4,
          confidence: 0.7,
          reason: "probe",
        },
      ],
    }) +
    "\n```";
  stubFetch(
    () => new Response(JSON.stringify(payload(fenced)), { status: 200 }),
  );

  const result = await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA],
  });
  assert.equal(result.results[0].label, "negative");
});

serialTest(
  "a non-object JSON body is still a missing-results error",
  async () => {
    stubFetch(
      () =>
        new Response(JSON.stringify(payload('"just a string"')), {
          status: 200,
        }),
    );

    await assert.rejects(
      classifyArticles({
        ticker: "TSLA",
        articles: [ARTICLE],
        providers: [OLLAMA],
      }),
      (error: unknown) =>
        error instanceof UpstreamError &&
        error.message.includes("missing its results"),
    );
  },
);

serialTest("an empty provider chain is a ConfigError", async () => {
  await assert.rejects(
    classifyArticles({ ticker: "TSLA", articles: [ARTICLE], providers: [] }),
    ConfigError,
  );
});

serialTest(
  "sends the bounded Ollama batch through Chat Completions",
  async () => {
    const calls = stubFetch((url, init) => {
      assert.equal(url, "https://ollama.com/v1/chat/completions");
      assert.equal(
        new Headers(init?.headers).get("authorization"),
        "Bearer k1",
      );
      const body = JSON.parse(String(init?.body));
      assert.equal(body.model, OLLAMA.model);
      assert.equal(body.max_tokens, 3200);
      assert.equal(body.reasoning_effort, "none");
      assert.equal(body.store, false);
      assert.equal(body.stream, false);
      assert.equal(body.response_format, undefined);
      assert.equal(body.tools, undefined);
      assert.equal(init?.cache, "no-store");
      const input = JSON.parse(
        body.messages.find((item: { role: string }) => item.role === "user")
          .content,
      );
      assert.equal(input.ticker, "TSLA");
      assert.equal(input.articles[0].article_id, "a1");
      assert.ok(input.articles[0].title.length <= 220);
      assert.ok(input.articles[0].description.length <= 900);
      return new Response(JSON.stringify(payload(OK_TEXT)));
    });
    await classifyArticles({
      ticker: "TSLA",
      articles: [
        { ...ARTICLE, title: "x".repeat(500), description: "y".repeat(2000) },
      ],
      providers: [OLLAMA],
    });
    assert.equal(calls.length, 1);
  },
);

serialTest(
  "keeps the gateway Responses schema and server-selected model",
  async () => {
    stubFetch((url, init) => {
      assert.equal(url, "https://ai-gateway.vercel.sh/v1/responses");
      assert.equal(
        new Headers(init?.headers).get("authorization"),
        "Bearer k2",
      );
      const body = JSON.parse(String(init?.body));
      assert.equal(body.model, GATEWAY.model);
      assert.equal(body.max_output_tokens, 3200);
      assert.equal(body.text.format.type, "json_schema");
      assert.equal(body.text.format.strict, true);
      assert.ok(body.text.format.schema.required.includes("results"));
      assert.equal(body.reasoning, undefined);
      assert.equal(body.store, false);
      return new Response(JSON.stringify(payload(OK_TEXT, true)));
    });
    const result = await classifyArticles({
      ticker: "TSLA",
      articles: [ARTICLE],
      providers: [GATEWAY],
    });
    assert.equal(result.results[0].classified, true);
  },
);

serialTest(
  "concurrent classifications keep distinct provider clients and credentials",
  async () => {
    const second = {
      ...OLLAMA,
      apiKey: "second-key",
      baseUrl: "https://second.example/v1",
      model: "second-model",
    };
    stubFetch(async (url, init) => {
      await Promise.resolve();
      const body = JSON.parse(String(init?.body));
      const expected = url.includes("second.example") ? second : OLLAMA;
      assert.equal(body.model, expected.model);
      assert.equal(
        new Headers(init?.headers).get("authorization"),
        `Bearer ${expected.apiKey}`,
      );
      return new Response(JSON.stringify(payload(OK_TEXT)));
    });
    const results = await Promise.all(
      [OLLAMA, second].map((provider) =>
        classifyArticles({
          ticker: "TSLA",
          articles: [ARTICLE],
          providers: [provider],
        }),
      ),
    );
    assert.ok(results.every((result) => result.results[0].classified));
  },
);

serialTest(
  "transient retries consume the shared budget with no SDK retry multiplication",
  async () => {
    let now = 0;
    const timeouts: number[] = [];
    const calls = stubFetch(() => {
      now += 5_000;
      return new Response("unavailable", { status: 503 });
    });
    await assert.rejects(
      __testOnly.classifyArticlesWithDeadline(
        { ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA] },
        {
          now: () => now,
          timeoutSignal: (ms) => {
            timeouts.push(ms);
            return new AbortController().signal;
          },
          sleep: async (ms) => {
            now += ms;
          },
        },
      ),
      UpstreamError,
    );
    assert.equal(calls.length, 3);
    assert.deepEqual(timeouts, [45_000, 39_200, 32_600]);
  },
);

serialTest(
  "an aborted SDK request cannot continue retries or fallback",
  async () => {
    let now = 0;
    let requestSignal: AbortSignal | null = null;
    const calls = stubFetch(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          requestSignal = init?.signal ?? null;
          init?.signal?.addEventListener("abort", () => {
            now = 45_000;
            reject(new DOMException("aborted", "AbortError"));
          });
        }),
    );
    await assert.rejects(
      __testOnly.classifyArticlesWithDeadline(
        { ticker: "TSLA", articles: [ARTICLE], providers: [OLLAMA, GATEWAY] },
        {
          now: () => now,
          timeoutSignal: () => {
            const controller = new AbortController();
            setImmediate(() => controller.abort());
            return controller.signal;
          },
        },
      ),
      (error: unknown) =>
        error instanceof UpstreamError && error.message.includes("timed out"),
    );
    assert.equal(calls.length, 1);
    assert.ok((requestSignal as AbortSignal | null)?.aborted);
  },
);

serialTest(
  "rejects incomplete output even when its JSON happens to parse",
  async () => {
    for (const provider of [OLLAMA, GATEWAY]) {
      stubFetch(() => {
        const body = payload(OK_TEXT, provider.name === "gateway");
        if (body.choices) body.choices[0].finish_reason = "length";
        else body.status = "incomplete";
        return new Response(JSON.stringify(body));
      });
      await assert.rejects(
        classifyArticles({
          ticker: "TSLA",
          articles: [ARTICLE],
          providers: [provider],
        }),
        (error: unknown) =>
          error instanceof UpstreamError &&
          error.message.includes("output limit"),
      );
    }
  },
);

serialTest("accepts bare arrays and nested article-keyed results", async () => {
  const rows = JSON.parse(OK_TEXT).results;
  for (const shape of [
    rows,
    { results: { a1: { ...rows[0], article_id: undefined } } },
  ]) {
    stubFetch(
      () => new Response(JSON.stringify(payload(JSON.stringify(shape)))),
    );
    const result = await classifyArticles({
      ticker: "TSLA",
      articles: [ARTICLE],
      providers: [OLLAMA],
    });
    assert.equal(result.results[0].classified, true);
    assert.equal(result.results[0].articleId, "a1");
  }
});

serialTest(
  "empty batches do not require credentials or make requests",
  async () => {
    const calls = stubFetch(() => {
      throw new Error("unexpected request");
    });
    assert.deepEqual(
      await classifyArticles({ ticker: "TSLA", articles: [], providers: [] }),
      { results: [], warnings: [] },
    );
    assert.equal(calls.length, 0);
  },
);

serialTest(
  "never exposes provider error bodies in user-facing failures",
  async () => {
    const marker = "sensitive-provider-debug-details";
    stubFetch(
      () =>
        new Response(JSON.stringify({ error: { message: marker } }), {
          status: 400,
        }),
    );
    await assert.rejects(
      classifyArticles({
        ticker: "TSLA",
        articles: [ARTICLE],
        providers: [OLLAMA],
      }),
      (error: unknown) =>
        error instanceof UpstreamError &&
        error.message.includes("HTTP 400") &&
        !error.message.includes(marker),
    );
  },
);

serialTest("classifications do not emit workflow or model traces", async () => {
  let events = 0;
  addTraceProcessor({
    onTraceStart: async () => {
      events += 1;
    },
    onTraceEnd: async () => {
      events += 1;
    },
    onSpanStart: async () => {
      events += 1;
    },
    onSpanEnd: async () => {
      events += 1;
    },
    shutdown: async () => {},
    forceFlush: async () => {},
  });
  stubFetch(() => new Response(JSON.stringify(payload(OK_TEXT))));
  await classifyArticles({
    ticker: "TSLA",
    articles: [ARTICLE],
    providers: [OLLAMA],
  });
  assert.equal(events, 0);
});

serialTest(
  "news through the SDK retains evidence coverage and limited-evidence holds",
  async () => {
    const overrides = {
      AI_MODEL: OLLAMA.model,
      AI_FALLBACK_MODEL: "",
      OLLAMA_API_KEY: "fixture-key",
      NEWSAPI_KEY: "",
    };
    const previous = Object.fromEntries(
      Object.keys(overrides).map((name) => [name, process.env[name]]),
    );
    Object.assign(process.env, overrides);
    let classifiedCount = 5;
    const calls = stubFetch((url, init) => {
      if (url.startsWith("https://news.google.com/rss/")) {
        return new Response(
          `<rss><channel>${Array.from(
            { length: 5 },
            (_, index) =>
              `<item><title>Headline ${index}</title><link>https://example.com/${index}</link><description>Fixture news</description><source>Example</source></item>`,
          ).join("")}</channel></rss>`,
        );
      }
      assert.equal(url, "https://ollama.com/v1/chat/completions");
      const body = JSON.parse(String(init?.body));
      const input = JSON.parse(
        body.messages.find((item: { role: string }) => item.role === "user")
          .content,
      );
      const text = JSON.stringify({
        results: input.articles
          .slice(0, classifiedCount)
          .map((article: { article_id: string }) => ({
            article_id: article.article_id,
            label: "positive",
            score: 0.8,
            confidence: 0.8,
            reason: "Fixture positive catalyst",
          })),
      });
      return new Response(JSON.stringify(payload(text)));
    });
    try {
      const complete = await analyze(" tsla ");
      assert.equal(complete.summary.ticker, "TSLA");
      assert.equal(complete.summary.articles_analyzed, 5);
      assert.equal(complete.evidence.coverage, 1);
      assert.equal(complete.evidence.grade, "strong");
      assert.equal(complete.evidence.drivers.length, 3);
      assert.equal(complete.summary.classification_degraded, false);
      assert.ok(complete.articles.every((article) => article.classified));

      classifiedCount = 2;
      const partial = await analyze("TSLA");
      assert.equal(partial.summary.articles_analyzed, 2);
      assert.equal(partial.evidence.coverage, 0.4);
      assert.equal(partial.evidence.grade, "limited");
      assert.equal(partial.summary.signal, "hold");
      assert.equal(partial.summary.classification_degraded, true);
      assert.equal(
        partial.articles.filter((article) => article.classified).length,
        2,
      );
      assert.equal(
        calls.length,
        4,
        "one news fetch and one model request per analysis",
      );
    } finally {
      for (const [name, value] of Object.entries(previous)) {
        if (value === undefined) delete process.env[name];
        else process.env[name] = value;
      }
    }
  },
);

serialTest(
  "ambient OpenAI headers cannot override or leak into provider requests",
  async () => {
    const overrides = {
      OPENAI_CUSTOM_HEADERS:
        "Authorization: Bearer unrelated-fixture-key\nX-Private-Header: unrelated-private-data\nOpenAI-Organization: unrelated-header-org",
      OPENAI_ORG_ID: "unrelated-org",
      OPENAI_PROJECT_ID: "unrelated-project",
    };
    const previous = Object.fromEntries(
      Object.keys(overrides).map((name) => [name, process.env[name]]),
    );
    Object.assign(process.env, overrides);
    stubFetch((url, init) => {
      const headers = new Headers(init?.headers);
      const provider = url.includes("ai-gateway") ? GATEWAY : OLLAMA;
      assert.equal(headers.get("authorization"), `Bearer ${provider.apiKey}`);
      assert.equal(headers.get("openai-organization"), null);
      assert.equal(headers.get("openai-project"), null);
      assert.equal(headers.get("x-private-header"), null);
      return new Response(
        JSON.stringify(payload(OK_TEXT, provider.name === "gateway")),
      );
    });
    try {
      for (const provider of [OLLAMA, GATEWAY]) {
        await classifyArticles({
          ticker: "TSLA",
          articles: [ARTICLE],
          providers: [provider],
        });
      }
    } finally {
      for (const [name, value] of Object.entries(previous)) {
        if (value === undefined) delete process.env[name];
        else process.env[name] = value;
      }
    }
  },
);

serialTest(
  "rejects filtered output even when its JSON is parseable",
  async () => {
    stubFetch(() => {
      const body = payload(OK_TEXT);
      body.choices![0].finish_reason = "content_filter";
      return new Response(JSON.stringify(body));
    });
    await assert.rejects(
      classifyArticles({
        ticker: "TSLA",
        articles: [ARTICLE],
        providers: [OLLAMA],
      }),
      (error: unknown) =>
        error instanceof UpstreamError &&
        error.message.includes("could not complete"),
    );
  },
);

serialTest(
  "model refusals produce a handled upstream failure without exposing refusal text",
  async () => {
    const refusal = "provider refusal fixture";
    for (const provider of [OLLAMA, GATEWAY]) {
      stubFetch(
        () =>
          new Response(
            JSON.stringify(
              provider.name === "ollama"
                ? {
                    id: "chat_refusal",
                    choices: [
                      {
                        index: 0,
                        finish_reason: "stop",
                        message: { role: "assistant", content: null, refusal },
                      },
                    ],
                  }
                : {
                    id: "resp_refusal",
                    status: "completed",
                    output: [
                      {
                        id: "msg_refusal",
                        type: "message",
                        role: "assistant",
                        status: "completed",
                        content: [{ type: "refusal", refusal }],
                      },
                    ],
                  },
            ),
          ),
      );
      await assert.rejects(
        classifyArticles({
          ticker: "TSLA",
          articles: [ARTICLE],
          providers: [provider],
        }),
        (error: unknown) =>
          error instanceof UpstreamError && !error.message.includes(refusal),
      );
    }
  },
);
