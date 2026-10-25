import assert from "node:assert/strict";
import { test } from "node:test";

import { clientKey, rateLimit } from "./rate-limit";

// The limiter allows 10 requests per 60-second window per key (see
// rate-limit.ts). Every test uses its own key because buckets are
// module-level state shared across calls in this process.
const T0 = 1_700_000_000_000;

test("the first request in a window is allowed", () => {
  assert.deepEqual(rateLimit("first-request", T0), {
    allowed: true,
    retryAfterSeconds: 0,
  });
});

test("the tenth request in a window is still allowed", () => {
  for (let i = 0; i < 9; i += 1) rateLimit("ten-allowed", T0);
  assert.deepEqual(rateLimit("ten-allowed", T0 + 1_000), {
    allowed: true,
    retryAfterSeconds: 0,
  });
});

test("the eleventh request in a window is rejected until the window resets", () => {
  for (let i = 0; i < 10; i += 1) rateLimit("eleventh-rejected", T0);
  assert.deepEqual(rateLimit("eleventh-rejected", T0 + 1_000), {
    allowed: false,
    retryAfterSeconds: 59,
  });
});

test("retryAfterSeconds counts down with the window and never drops below 1", () => {
  for (let i = 0; i < 10; i += 1) rateLimit("retry-countdown", T0);
  assert.equal(rateLimit("retry-countdown", T0 + 30_000).retryAfterSeconds, 30);
  assert.equal(rateLimit("retry-countdown", T0 + 59_500).retryAfterSeconds, 1);
});

test("rejected requests do not extend the window", () => {
  for (let i = 0; i < 10; i += 1) rateLimit("no-extension", T0);
  assert.equal(rateLimit("no-extension", T0 + 30_000).allowed, false);
  // The original window still ends at T0 + 60s, not 30s after the rejection.
  assert.deepEqual(rateLimit("no-extension", T0 + 60_000), {
    allowed: true,
    retryAfterSeconds: 0,
  });
});

test("a request after the window expires starts a fresh window", () => {
  for (let i = 0; i < 10; i += 1) rateLimit("fresh-window", T0);
  assert.equal(rateLimit("fresh-window", T0 + 60_000).allowed, true);
  for (let i = 0; i < 9; i += 1) rateLimit("fresh-window", T0 + 60_100);
  assert.equal(rateLimit("fresh-window", T0 + 60_200).allowed, false);
});

test("limits are tracked per key", () => {
  for (let i = 0; i < 10; i += 1) rateLimit("exhausted-key", T0);
  assert.equal(rateLimit("exhausted-key", T0).allowed, false);
  assert.equal(rateLimit("other-key", T0).allowed, true);
});

test("clientKey prefers the first x-forwarded-for entry", () => {
  const request = new Request("http://localhost/api/analyze", {
    headers: {
      "x-forwarded-for": "203.0.113.7, 10.0.0.1",
      "x-real-ip": "198.51.100.3",
    },
  });
  assert.equal(clientKey(request), "203.0.113.7");
});

test("clientKey falls back to x-real-ip, then to unknown", () => {
  const realIp = new Request("http://localhost/api/analyze", {
    headers: { "x-real-ip": "198.51.100.3" },
  });
  assert.equal(clientKey(realIp), "198.51.100.3");

  const bare = new Request("http://localhost/api/analyze");
  assert.equal(clientKey(bare), "unknown");
});

test("clientKey ignores an empty first x-forwarded-for entry", () => {
  const request = new Request("http://localhost/api/analyze", {
    headers: { "x-forwarded-for": " , 10.0.0.1", "x-real-ip": "198.51.100.9" },
  });
  assert.equal(clientKey(request), "198.51.100.9");
});
