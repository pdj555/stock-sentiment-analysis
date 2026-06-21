import assert from "node:assert/strict";
import test from "node:test";

import { extractJson, normalizeClassification } from "./agent";
import type { RawArticle } from "./news";

function article(id: string): RawArticle {
  return {
    articleId: id,
    title: `Title ${id}`,
    description: `Description ${id}`,
    url: `https://example.com/${id}`,
    source: "Example",
    publishedAt: new Date("2026-01-01T00:00:00Z"),
  };
}

const A = article("a");
const B = article("b");

test("coerces score to the label's sign and clamps ranges", () => {
  const { results, warnings } = normalizeClassification(
    [
      { article_id: "a", label: "positive", score: -0.4, confidence: 0.9, reason: "good" },
      { article_id: "b", label: "negative", score: 0.7, confidence: 2, reason: "bad" },
    ],
    [A, B],
  );

  assert.equal(warnings.length, 0);
  // positive => abs(score)
  assert.deepEqual(
    results.find((r) => r.articleId === "a"),
    { articleId: "a", label: "positive", score: 0.4, confidence: 0.9, reason: "good" },
  );
  // negative => -abs(score); confidence clamped to [0,1]
  assert.deepEqual(
    results.find((r) => r.articleId === "b"),
    { articleId: "b", label: "negative", score: -0.7, confidence: 1, reason: "bad" },
  );
});

test("neutral forces a zero score", () => {
  const { results } = normalizeClassification(
    [{ article_id: "a", label: "neutral", score: 0.8, confidence: 0.5, reason: "" }],
    [A],
  );
  const row = results[0];
  assert.equal(row.label, "neutral");
  assert.equal(row.score, 0);
  assert.equal(row.reason, null); // blank reason becomes null
});

test("clamps out-of-range scores to [-1, 1]", () => {
  const { results } = normalizeClassification(
    [{ article_id: "a", label: "positive", score: 5, confidence: 0.5, reason: "x" }],
    [A],
  );
  assert.equal(results[0].score, 1);
});

test("backfills a skipped article as neutral and warns", () => {
  const { results, warnings } = normalizeClassification(
    [{ article_id: "a", label: "positive", score: 0.5, confidence: 0.6, reason: "x" }],
    [A, B],
  );
  const b = results.find((r) => r.articleId === "b");
  assert.deepEqual(b, {
    articleId: "b",
    label: "neutral",
    score: 0,
    confidence: 0,
    reason: "No classification returned for this article.",
  });
  assert.ok(warnings.some((w) => w.includes("skipped 1 article")));
});

test("ignores duplicate ids, keeping the first, and warns", () => {
  const { results, warnings } = normalizeClassification(
    [
      { article_id: "a", label: "positive", score: 0.5, confidence: 0.6, reason: "first" },
      { article_id: "a", label: "negative", score: 0.9, confidence: 0.9, reason: "second" },
    ],
    [A],
  );
  assert.equal(results.length, 1);
  assert.equal(results[0].label, "positive");
  assert.equal(results[0].reason, "first");
  assert.ok(warnings.some((w) => w.includes("duplicate")));
});

test("ignores results for unrequested articles and warns", () => {
  const { results, warnings } = normalizeClassification(
    [
      { article_id: "a", label: "positive", score: 0.5, confidence: 0.6, reason: "x" },
      { article_id: "zzz", label: "positive", score: 0.5, confidence: 0.6, reason: "x" },
    ],
    [A],
  );
  assert.equal(results.length, 1);
  assert.ok(warnings.some((w) => w.includes("unexpected")));
});

test("drops unreadable rows (bad label or non-finite numbers) and warns", () => {
  const { results, warnings } = normalizeClassification(
    [
      { article_id: "a", label: "bullish", score: 0.5, confidence: 0.6, reason: "x" },
      { article_id: "b", label: "positive", score: Number.NaN, confidence: 0.6, reason: "x" },
    ],
    [A, B],
  );
  // both invalid => both backfilled neutral
  assert.ok(results.every((r) => r.label === "neutral"));
  assert.ok(warnings.some((w) => w.includes("unreadable")));
});

test("an empty batch yields no results and no warnings", () => {
  assert.deepEqual(normalizeClassification([], []), { results: [], warnings: [] });
});

const EXPECTED = { results: [{ article_id: "a", label: "positive" }] };

test("extractJson parses a plain JSON object", () => {
  assert.deepEqual(extractJson(JSON.stringify(EXPECTED)), EXPECTED);
});

test("extractJson strips markdown code fences", () => {
  const text = "```json\n" + JSON.stringify(EXPECTED) + "\n```";
  assert.deepEqual(extractJson(text), EXPECTED);
});

test("extractJson ignores <think> reasoning blocks", () => {
  const text = `<think>let me reason about TSLA news…</think>\n${JSON.stringify(EXPECTED)}`;
  assert.deepEqual(extractJson(text), EXPECTED);
});

test("extractJson recovers JSON wrapped in surrounding prose", () => {
  const text = `Here is the result:\n${JSON.stringify(EXPECTED)}\nHope that helps!`;
  assert.deepEqual(extractJson(text), EXPECTED);
});

test("extractJson returns null when there is no JSON", () => {
  assert.equal(extractJson("I could not classify these articles."), null);
  assert.equal(extractJson(""), null);
});
