import assert from "node:assert/strict";
import { test } from "node:test";

import { isFallbackEligible, resolveProviders } from "./providers";

function envFrom(values: Record<string, string>) {
  return (name: string) => values[name] ?? "";
}

test("a bare model id routes to cheap Ollama Cloud", () => {
  const [primary] = resolveProviders(
    envFrom({ AI_MODEL: "gpt-oss:20b", OLLAMA_API_KEY: "k" }),
  );
  assert.equal(primary.name, "ollama");
  assert.equal(primary.baseUrl, "https://ollama.com/v1");
  assert.equal(primary.model, "gpt-oss:20b");
});

test("a provider/model id routes to the Vercel gateway", () => {
  const [primary] = resolveProviders(
    envFrom({ AI_MODEL: "anthropic/claude-sonnet-5", AI_GATEWAY_API_KEY: "k" }),
  );
  assert.equal(primary.name, "gateway");
  assert.equal(primary.baseUrl, "https://ai-gateway.vercel.sh/v1");
  assert.equal(primary.model, "anthropic/claude-sonnet-5");
});

test("the gateway falls back to the Vercel OIDC token when no key is set", () => {
  const [primary] = resolveProviders(
    envFrom({ AI_MODEL: "openai/gpt-5.6-sol", VERCEL_OIDC_TOKEN: "oidc" }),
  );
  assert.equal(primary.name, "gateway");
  assert.equal(primary.apiKey, "oidc");
});

test("AI_FALLBACK_MODEL adds a second route", () => {
  const providers = resolveProviders(
    envFrom({
      AI_MODEL: "gpt-oss:120b",
      AI_FALLBACK_MODEL: "anthropic/claude-sonnet-5",
      OLLAMA_API_KEY: "k1",
      AI_GATEWAY_API_KEY: "k2",
    }),
  );
  assert.deepEqual(
    providers.map((p) => p.name),
    ["ollama", "gateway"],
  );
});

test("older OLLAMA_MODEL / OPENAI_MODEL still work when AI_MODEL is unset", () => {
  const [primary] = resolveProviders(
    envFrom({ OLLAMA_MODEL: "gpt-oss:120b", OLLAMA_API_KEY: "k" }),
  );
  assert.equal(primary.name, "ollama");
  assert.equal(primary.model, "gpt-oss:120b");
});

test("a route with no key is dropped", () => {
  assert.deepEqual(resolveProviders(envFrom({ AI_MODEL: "gpt-oss:120b" })), []);
});

test("unset model env defaults to free Ollama gpt-oss:120b", () => {
  const [primary] = resolveProviders(envFrom({ OLLAMA_API_KEY: "k" }));
  assert.equal(primary.name, "ollama");
  assert.equal(primary.model, "gpt-oss:120b");
});

test("fallback eligibility covers auth, quota, not-found, and 5xx but not 400", () => {
  for (const status of [401, 403, 404, 429, 500, 502, 503]) {
    assert.equal(isFallbackEligible(status), true, `expected ${status} eligible`);
  }
  for (const status of [400, 200]) {
    assert.equal(isFallbackEligible(status), false, `expected ${status} not eligible`);
  }
});
