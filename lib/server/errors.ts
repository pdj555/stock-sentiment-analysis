/**
 * Typed errors that map cleanly onto HTTP responses in the analyze route.
 *
 * - {@link ConfigError} — the request or environment is misconfigured (400).
 * - {@link UpstreamError} — a dependency (news source, model) failed (502).
 *
 * Anything else that escapes is treated as an unexpected 500.
 */

export class ConfigError extends Error {
  readonly status = 400 as const;

  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

export class UpstreamError extends Error {
  readonly status = 502 as const;

  constructor(message: string) {
    super(message);
    this.name = "UpstreamError";
  }
}
