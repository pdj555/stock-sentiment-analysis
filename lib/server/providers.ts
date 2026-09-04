/**
 * AI provider resolution and fallback policy.
 *
 * The active model id decides where the request goes: a bare id (`gpt-oss:120b`)
 * runs on free Ollama Cloud; a `provider/model` id (`anthropic/claude-sonnet-5`,
 * `openai/gpt-5.6-sol`) runs on the Vercel AI Gateway. Both speak the OpenAI
 * Responses API, so the request shape in `openai.ts` is identical. `AI_MODEL`
 * sets the primary; `AI_FALLBACK_MODEL` optionally adds a second route for when
 * the primary is capped or down. Unset model env falls back to
 * `DEFAULT_OLLAMA_MODEL`.
 */

/** Free Ollama Cloud default when `AI_MODEL` / `OLLAMA_MODEL` / `OPENAI_MODEL` are unset. */
export const DEFAULT_OLLAMA_MODEL = "gpt-oss:120b";

export type ProviderName = "ollama" | "gateway";

export interface Provider {
  name: ProviderName;
  apiKey: string;
  baseUrl: string;
  model: string;
}

type Env = (name: string) => string;

/** Route a single model id to the provider that hosts it. */
function providerForModel(model: string, env: Env): Provider {
  if (model.includes("/")) {
    return {
      name: "gateway",
      apiKey: env("AI_GATEWAY_API_KEY") || env("VERCEL_OIDC_TOKEN"),
      baseUrl: env("AI_GATEWAY_BASE_URL") || "https://ai-gateway.vercel.sh/v1",
      model,
    };
  }
  return {
    name: "ollama",
    apiKey: env("OLLAMA_API_KEY"),
    baseUrl: env("OLLAMA_BASE_URL") || "https://ollama.com/v1",
    model,
  };
}

/**
 * Ordered provider chain from the active model config. `AI_MODEL` is the
 * primary (falling back to the older `OLLAMA_MODEL`/`OPENAI_MODEL` vars, then
 * `DEFAULT_OLLAMA_MODEL`); `AI_FALLBACK_MODEL` is an optional second route.
 * Only routes whose key is set are kept.
 */
export function resolveProviders(env: Env): Provider[] {
  const primary =
    env("AI_MODEL") ||
    env("OLLAMA_MODEL") ||
    env("OPENAI_MODEL") ||
    DEFAULT_OLLAMA_MODEL;
  const fallback = env("AI_FALLBACK_MODEL");

  const providers: Provider[] = [];
  const seen = new Set<string>();
  for (const model of [primary, fallback]) {
    if (!model || seen.has(model)) continue;
    seen.add(model);
    const provider = providerForModel(model, env);
    if (provider.apiKey) providers.push(provider);
  }
  return providers;
}

/**
 * Whether a provider's HTTP failure should fail over to the next provider.
 * 404 is included: a not-found endpoint or model is specific to that provider
 * (each hosts different models), so the next provider may still serve it.
 * 400 (malformed) is excluded — it would fail identically everywhere.
 */
export function isFallbackEligible(status: number): boolean {
  return (
    status === 401 ||
    status === 403 ||
    status === 404 ||
    status === 429 ||
    status >= 500
  );
}
