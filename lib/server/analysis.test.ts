import assert from "node:assert/strict";
import { test } from "node:test";

import { summarizeAnalysis } from "./analysis";
import type { ArticleSentiment } from "./openai";
import type { RawArticle } from "./news";

const AS_OF = new Date("2026-07-25T12:00:00.000Z");

function article(index: number): RawArticle {
  return {
    articleId: `a${index}`,
    title: `Headline ${index}`,
    description: `Description ${index}`,
    source: "Example",
    url: `https://example.com/${index}`,
    publishedAt: new Date(AS_OF.getTime() - index * 60_000),
  };
}

function fixture(options: {
  classified: number;
  missing: number;
  score: number;
}): Parameters<typeof summarizeAnalysis>[0] {
  const total = options.classified + options.missing;
  const articles = Array.from({ length: total }, (_, index) => article(index + 1));
  const results: ArticleSentiment[] = articles.map((item, index) => ({
    articleId: item.articleId,
    label: index < options.classified ? "positive" : "neutral",
    score: index < options.classified ? options.score : 0,
    confidence: index < options.classified ? 0.8 : 0,
    reason: index < options.classified ? "Positive catalyst" : "No classification returned",
    classified: index < options.classified,
  }));
  return {
    ticker: "TEST",
    source: "google-rss",
    articles,
    results,
    warnings: [],
    asOf: AS_OF,
  };
}

function mixedFixture(): Parameters<typeof summarizeAnalysis>[0] {
  const articles = [article(1), article(2), article(3), article(4)];
  const scores = [0.9, 0.7, 0.4, -0.85];
  const results: ArticleSentiment[] = articles.map((item, index) => ({
    articleId: item.articleId,
    label: scores[index] > 0 ? "positive" : "negative",
    score: scores[index],
    confidence: 0.8,
    reason: scores[index] > 0 ? "Positive catalyst" : "Material counter-signal",
    classified: true,
  }));
  return {
    ticker: "TEST",
    source: "google-rss",
    articles,
    results,
    warnings: [],
    asOf: AS_OF,
  };
}

test("holds when fewer than three classifications support the direction", () => {
  const result = summarizeAnalysis(fixture({ classified: 2, missing: 0, score: 0.8 }));
  assert.equal(result.evidence.grade, "limited");
  assert.equal(result.evidence.coverage, 1);
  assert.equal(result.summary.signal, "hold");
});

test("emits a strong directional signal from broad aligned evidence", () => {
  const result = summarizeAnalysis(fixture({ classified: 5, missing: 0, score: 0.8 }));
  assert.equal(result.evidence.grade, "strong");
  assert.equal(result.evidence.agreement, 1);
  assert.equal(result.summary.signal, "buy");
});

test("missing rows reduce coverage and never count as analyzed", () => {
  const result = summarizeAnalysis(fixture({ classified: 3, missing: 2, score: 0.8 }));
  assert.equal(result.evidence.coverage, 0.6);
  assert.equal(result.evidence.classified_articles, 3);
  assert.equal(result.summary.articles_analyzed, 3);
});

test("drivers retain the strongest counter-direction", () => {
  const result = summarizeAnalysis(mixedFixture());
  assert.deepEqual(
    new Set(result.evidence.drivers.map((driver) => driver.direction)),
    new Set(["positive", "negative"]),
  );
});

test("equal-impact drivers use article id order and retain a counter-direction", () => {
  const ids = ["a3", "a1", "a2", "a4"];
  const articles = ids.map((id) => ({
    ...article(1),
    articleId: id,
    title: `Headline ${id}`,
    url: `https://example.com/${id}`,
    publishedAt: AS_OF,
  }));
  const results: ArticleSentiment[] = ids.map((articleId) => ({
    articleId,
    label: articleId === "a2" ? "negative" : "positive",
    score: articleId === "a2" ? -0.8 : 0.8,
    confidence: 0.8,
    reason: "Equal-impact evidence",
    classified: true,
  }));

  const result = summarizeAnalysis({
    ticker: "TEST",
    source: "google-rss",
    articles,
    results,
    warnings: [],
    asOf: AS_OF,
  });

  assert.deepEqual(
    result.evidence.drivers.map((driver) => driver.article_id),
    ["a1", "a2", "a3"],
  );
  assert.deepEqual(
    result.evidence.drivers.map((driver) => driver.direction),
    ["positive", "negative", "positive"],
  );
});
