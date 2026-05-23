import assert from "node:assert/strict";
import { test } from "node:test";

import { isFallbackEligible, resolveProviders } from "./providers";

function envFrom(values: Record<string, string>) {
  return (name: string) => values[name] ?? "";
}

test("ollama is primary, openrouter is the fallback", () => {
  const providers = resolveProviders(
    envFrom({
      OLLAMA_API_KEY: "k1",
      OLLAMA_BASE_URL: "https://ollama.com/v1",
      OPENAI_MODEL: "gpt-oss:120b",
      OPENROUTER_API_KEY: "k2",
    }),
  );

  assert.deepEqual(
    providers.map((p) => p.name),
    ["ollama", "openrouter"],
  );
  assert.equal(providers[0].baseUrl, "https://ollama.com/v1");
  assert.equal(providers[0].model, "gpt-oss:120b");
  assert.equal(providers[1].baseUrl, "https://openrouter.ai/api/v1");
  assert.equal(providers[1].model, "openai/gpt-4o-mini");
});

test("only providers with a key are included", () => {
  const providers = resolveProviders(envFrom({ OPENROUTER_API_KEY: "k" }));
  assert.deepEqual(
    providers.map((p) => p.name),
    ["openrouter"],
  );
});

test("openai is the last resort", () => {
  const providers = resolveProviders(
    envFrom({
      OLLAMA_API_KEY: "a",
      OPENROUTER_API_KEY: "b",
      OPENAI_API_KEY: "c",
      OPENAI_MODEL: "m",
    }),
  );
  assert.deepEqual(
    providers.map((p) => p.name),
    ["ollama", "openrouter", "openai"],
  );
});

test("no keys yields an empty chain", () => {
  assert.deepEqual(resolveProviders(envFrom({})), []);
});

test("OPENROUTER_MODEL overrides the default", () => {
  const [openrouter] = resolveProviders(
    envFrom({ OPENROUTER_API_KEY: "k", OPENROUTER_MODEL: "anthropic/claude-3.5" }),
  );
  assert.equal(openrouter.model, "anthropic/claude-3.5");
});

test("fallback eligibility covers auth, quota, and 5xx but not 400", () => {
  for (const status of [401, 403, 429, 500, 502, 503]) {
    assert.equal(isFallbackEligible(status), true, `expected ${status} eligible`);
  }
  for (const status of [400, 404, 200]) {
    assert.equal(isFallbackEligible(status), false, `expected ${status} not eligible`);
  }
});
