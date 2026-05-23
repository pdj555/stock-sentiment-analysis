/**
 * AI provider resolution and fallback policy.
 *
 * Builds the ordered chain the classifier tries: Ollama (primary) →
 * OpenRouter (fallback) → OpenAI. Only providers whose API key is set are
 * included, so existing single-provider setups keep working. Every provider
 * speaks the Responses API, so the request shape in `openai.ts` is identical.
 */

export type ProviderName = "ollama" | "openrouter" | "openai";

export interface Provider {
  name: ProviderName;
  apiKey: string;
  baseUrl: string;
  model: string;
}

type Env = (name: string) => string;

/**
 * Ordered provider chain from the environment, keeping only those with a key.
 * Ollama/OpenAI fall back to `OPENAI_MODEL`; OpenRouter needs a model that
 * supports structured output (json_schema).
 */
export function resolveProviders(env: Env): Provider[] {
  const model = env("OPENAI_MODEL");
  const chain: Provider[] = [
    {
      name: "ollama",
      apiKey: env("OLLAMA_API_KEY"),
      baseUrl: env("OLLAMA_BASE_URL") || env("OPENAI_BASE_URL") || "https://ollama.com/v1",
      model: env("OLLAMA_MODEL") || model,
    },
    {
      name: "openrouter",
      apiKey: env("OPENROUTER_API_KEY"),
      baseUrl: env("OPENROUTER_BASE_URL") || "https://openrouter.ai/api/v1",
      model: env("OPENROUTER_MODEL") || "openai/gpt-4o-mini",
    },
    {
      name: "openai",
      apiKey: env("OPENAI_API_KEY"),
      baseUrl: env("OPENAI_BASE_URL") || "https://api.openai.com/v1",
      model,
    },
  ];
  return chain.filter((provider) => provider.apiKey);
}

/**
 * Whether a provider's HTTP failure should fail over to the next provider.
 * 400 (malformed) is excluded — it would fail identically everywhere.
 */
export function isFallbackEligible(status: number): boolean {
  return status === 401 || status === 403 || status === 429 || status >= 500;
}
