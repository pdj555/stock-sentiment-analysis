# Decision-Grade Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn every headline score into a conservative, evidence-backed decision brief that shows evidence quality, directional agreement, and the strongest supporting and opposing drivers.

**Architecture:** Keep the existing single batched model classification call. Add deterministic evidence aggregation beside the existing score in both TypeScript and Python, then render the same decision concepts on the Next.js product surface, CLI JSON/text output, and local Python UI. Missing model rows remain explicit unclassified evidence and can never strengthen a directional signal.

**Tech Stack:** Next.js 15, React 19, TypeScript 5.7, Node test runner, Python 3.11+ standard library, `unittest`.

## Global Constraints

- Make no additional AI or news requests per analysis; evidence aggregation must be deterministic and local.
- Add no runtime or development dependencies.
- Preserve the existing `buy | sell | hold` API values; user-facing copy may render them as `Bullish | Bearish | No edge`.
- Mark every valid model classification `classified: true` and every synthesized missing-row fallback `classified: false`.
- Evidence grade is `limited` when fewer than 3 articles are classified or coverage is below `0.60`.
- Evidence grade is `strong` only when at least 5 articles are classified, coverage is at least `0.80`, directional agreement is at least `0.70`, and aggregate confidence is at least `0.65`; otherwise sufficient evidence is `moderate`.
- A directional signal requires non-limited evidence, aggregate confidence of at least `0.55`, directional agreement of at least `0.55`, and absolute score above `0.15`; otherwise return `hold`.
- Directional agreement is `abs(sum(signed impact)) / sum(abs(signed impact))`, or `0` when directional impact is zero.
- Drivers exclude neutral and unclassified rows, are ranked by absolute `score * confidence * recency`, include at most 3 rows, and include the strongest counter-direction when both directions exist.
- Tests are offline and deterministic. Python remains standard-library-only.
- Never log, commit, or expose provider credentials.

---

## File Structure

- `lib/types.ts`: Public web/API evidence contracts.
- `lib/server/openai.ts`: Classification provenance for valid and synthesized rows.
- `lib/server/analysis.ts`: Deterministic evidence aggregation, conservative signal gating, and driver selection.
- `lib/server/analysis.test.ts`: TypeScript domain tests independent of network calls.
- `components/EvidenceBrief.tsx`: One focused decision-brief surface.
- `components/Results.tsx`: Result-page composition; removes false-precision gauge emphasis.
- `components/ScoreGauge.tsx`: Delete after its only use is removed.
- `lib/format.ts`: Honest signal and evidence copy.
- `lib/format.test.ts`: Copy and grade formatting contract tests.
- `app/globals.css`: Styles for the compact evidence brief and simplified verdict.
- `stock_sentiment/types.py`: Python evidence dataclasses and serialized contract.
- `stock_sentiment/sentiment.py`: Python parity for evidence aggregation and signal gating.
- `stock_sentiment/cli.py`: Decision-grade text output while preserving JSON compatibility.
- `stock_sentiment/ui.py`: Local UI payload and evidence metrics.
- `tests/test_sentiment_summary.py`: Python evidence math and signal-gating tests.
- `tests/test_sentiment_openai_contract.py`: Classification provenance tests.
- `tests/test_cli.py`: CLI evidence output tests.
- `tests/test_ui.py`: Local UI evidence payload tests.
- `README.md`: Concise product promise and output contract.

### Task 1: Web evidence engine and API contract

**Files:**
- Create: `lib/server/analysis.test.ts`
- Modify: `lib/types.ts`
- Modify: `lib/server/openai.ts`
- Modify: `lib/server/openai.test.ts`
- Modify: `lib/server/analysis.ts`
- Modify: `package.json`

**Interfaces:**
- Consumes: Existing `RawArticle`, `ArticleSentiment`, `AnalysisSummary`, and `AnalysisArticle` contracts.
- Produces: `EvidenceGrade`, `EvidenceDriver`, `EvidenceProfile`, `ArticleSentiment.classified`, `AnalysisArticle.classified`, `AnalysisResult.evidence`, and exported `summarizeAnalysis(input): Pick<AnalysisResult, "summary" | "evidence">`.

- [ ] **Step 1: Add the failing domain tests**

Create `lib/server/analysis.test.ts` with fixed timestamps and article helpers. Cover all four behaviors below:

```ts
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
```

Extend `lib/server/openai.test.ts` to assert a valid returned row has `classified === true` and a missing row synthesized by `classifyArticles` has `classified === false`.

- [ ] **Step 2: Run the TypeScript tests and verify the new contract fails**

Run: `npm test`

Expected: FAIL because `summarizeAnalysis`, `classified`, and evidence types do not exist.

- [ ] **Step 3: Add explicit evidence contracts**

Add these contracts to `lib/types.ts` and attach `evidence` to `AnalysisResult`:

```ts
export type EvidenceGrade = "limited" | "moderate" | "strong";

export interface EvidenceDriver {
  article_id: string;
  title: string;
  url: string | null;
  source: string | null;
  published_at: string | null;
  direction: "positive" | "negative";
  impact: number;
  confidence: number;
  reason: string | null;
}

export interface EvidenceProfile {
  grade: EvidenceGrade;
  coverage: number;
  agreement: number;
  classified_articles: number;
  total_articles: number;
  drivers: EvidenceDriver[];
}
```

Add `classified: boolean` to `AnalysisArticle`. Add `classified: boolean` to the server-only `ArticleSentiment` interface. Normalized model rows use `true`; missing-row neutral fallbacks use `false`.

- [ ] **Step 4: Implement deterministic aggregation and conservative gating**

Replace the private summary-only helper with an exported helper that returns both objects:

```ts
export function summarizeAnalysis(input: {
  ticker: string;
  source: NewsSource;
  articles: RawArticle[];
  results: ArticleSentiment[];
  warnings: string[];
  asOf: Date;
}): Pick<AnalysisResult, "summary" | "evidence">;
```

Use the global thresholds verbatim. Compute each signed impact as `result.score * recency * clamp(result.confidence, 0, 1)`. Compute coverage from `classified === true`, set `articles_analyzed` to that classified count, and include `classified` in each article payload. Driver selection must use this exact shape and deterministic tie-break:

```ts
const ranked = candidates.sort(
  (left, right) =>
    Math.abs(right.impact) - Math.abs(left.impact) ||
    left.article_id.localeCompare(right.article_id),
);
```

Start with the strongest driver. If the ranked set contains the opposite direction, add its strongest row next, then fill remaining slots in ranked order without duplicates. Return no more than 3.

- [ ] **Step 5: Add the analysis test file to the standard web test command**

Set the package script to:

```json
"test": "tsx --test lib/server/analysis.test.ts lib/server/providers.test.ts lib/server/openai.test.ts"
```

- [ ] **Step 6: Run focused and full web verification**

Run: `npx tsx --test lib/server/analysis.test.ts lib/server/openai.test.ts`

Expected: all evidence and classification provenance tests PASS.

Run: `npm test`

Expected: all current web tests PASS.

- [ ] **Step 7: Commit the evidence engine**

```bash
git add lib/types.ts lib/server/openai.ts lib/server/openai.test.ts lib/server/analysis.ts lib/server/analysis.test.ts package.json
git commit -m "Add decision-grade evidence analysis"
```

### Task 2: Minimal decision brief product surface

**Files:**
- Create: `components/EvidenceBrief.tsx`
- Create: `lib/format.test.ts`
- Modify: `components/Results.tsx`
- Delete: `components/ScoreGauge.tsx`
- Modify: `lib/format.ts`
- Modify: `app/globals.css`
- Modify: `package.json`

**Interfaces:**
- Consumes: `AnalysisResult.evidence`, `EvidenceProfile`, and existing signal values from Task 1.
- Produces: `EvidenceBrief({ evidence, signal })`, honest signal copy, evidence-grade copy, and a result page with one clear conclusion followed by auditable drivers.

- [ ] **Step 1: Add failing copy contract tests**

Create `lib/format.test.ts`:

```ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { evidenceGradeLabel, SIGNAL_COPY } from "./format";

test("renders trading values as research conclusions", () => {
  assert.equal(SIGNAL_COPY.buy.word, "Bullish");
  assert.equal(SIGNAL_COPY.sell.word, "Bearish");
  assert.equal(SIGNAL_COPY.hold.word, "No edge");
});

test("formats every evidence grade", () => {
  assert.equal(evidenceGradeLabel("limited"), "Limited");
  assert.equal(evidenceGradeLabel("moderate"), "Moderate");
  assert.equal(evidenceGradeLabel("strong"), "Strong");
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `npx tsx --test lib/format.test.ts`

Expected: FAIL because `evidenceGradeLabel` and the new copy do not exist.

- [ ] **Step 3: Replace false-precision copy with research-grade language**

Update `SIGNAL_COPY` to these exact words and lines:

```ts
export const SIGNAL_COPY = {
  buy: { word: "Bullish", line: "Recent coverage supports a bullish near-term read." },
  sell: { word: "Bearish", line: "Recent coverage supports a bearish near-term read." },
  hold: { word: "No edge", line: "The evidence is limited, mixed, or below the conviction threshold." },
} satisfies Record<Signal, { word: string; line: string }>;
```

Add `evidenceGradeLabel(grade: EvidenceGrade): string` with title-case output.

- [ ] **Step 4: Build the focused evidence brief**

Create `EvidenceBrief.tsx` with one header row, three compact metrics, and an optional driver list. Use:

```tsx
<section className="evidence-brief nous-panel" aria-labelledby="evidence-title">
  <header className="evidence-head">
    <div>
      <span className="panel-legend">Decision brief</span>
      <h3 id="evidence-title">{SIGNAL_COPY[signal].word}</h3>
      <p>{SIGNAL_COPY[signal].line}</p>
    </div>
    <span className={`evidence-grade grade-${evidence.grade}`}>
      {evidenceGradeLabel(evidence.grade)} evidence
    </span>
  </header>
  <dl className="evidence-metrics">
    <div><dt>Coverage</dt><dd>{formatConfidence(evidence.coverage)}</dd></div>
    <div><dt>Agreement</dt><dd>{formatConfidence(evidence.agreement)}</dd></div>
    <div><dt>Classified</dt><dd>{evidence.classified_articles}/{evidence.total_articles}</dd></div>
  </dl>
  {evidence.drivers.length > 0 && (
    <div className="evidence-driver-wrap">
      <h4>Key drivers</h4>
      <ol className="evidence-drivers">
        {evidence.drivers.map((driver) => (
          <li key={driver.article_id} className={`driver-${driver.direction}`}>
            <span className="driver-direction">
              {driver.direction === "positive" ? "Supports" : "Counters"}
            </span>
            <div>
              <h5>
                {driver.url ? (
                  <a href={driver.url} target="_blank" rel="noreferrer noopener">
                    {driver.title}
                  </a>
                ) : driver.title}
              </h5>
              <p>{[driver.source, driver.reason].filter(Boolean).join(" · ")}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )}
</section>
```

Each driver row must show direction, linked headline when a URL exists, source, and reason. Do not repeat score or confidence in the driver row; the article list retains those details.

- [ ] **Step 5: Simplify the result hierarchy**

In `Results.tsx`, remove `ScoreGauge`, delete `components/ScoreGauge.tsx`, and make `EvidenceBrief` the first content after the ticker header. Keep one compact metrics panel with score, confidence, headline count, and lookback. Keep warnings before the full article list. Render the raw API values nowhere in user-facing copy.

In `app/globals.css`, remove unused `.gauge*` rules and add responsive `.evidence-*` rules. Use existing color variables, borders, spacing, and typography; do not introduce a new visual language or animation dependency. At widths below `680px`, stack the header and use a single-column driver layout.

- [ ] **Step 6: Run product-surface verification**

Set the final package script to:

```json
"test": "tsx --test lib/format.test.ts lib/server/analysis.test.ts lib/server/providers.test.ts lib/server/openai.test.ts"
```

Run: `npm test`

Expected: all web tests PASS.

Run: `npm run build`

Expected: Next.js production build and type checking PASS with no unused `ScoreGauge` import.

- [ ] **Step 7: Commit the decision brief UI**

```bash
git add components/EvidenceBrief.tsx components/Results.tsx components/ScoreGauge.tsx lib/format.ts lib/format.test.ts app/globals.css package.json
git commit -m "Present an auditable decision brief"
```

### Task 3: Python parity, local UI, and documentation

**Files:**
- Modify: `stock_sentiment/types.py`
- Modify: `stock_sentiment/sentiment.py`
- Modify: `stock_sentiment/cli.py`
- Modify: `stock_sentiment/ui.py`
- Modify: `tests/test_sentiment_summary.py`
- Modify: `tests/test_sentiment_openai_contract.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_ui.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: Thresholds and evidence semantics from Task 1.
- Produces: `EvidenceDriver`, `EvidenceProfile`, `ArticleSentiment.classified`, `SentimentSummary.evidence`, serialized CLI evidence, and local UI evidence metrics matching the web product.

- [ ] **Step 1: Add failing Python parity tests**

Extend `tests/test_sentiment_summary.py` with fixed `NewsArticle` and `ArticleSentiment` fixtures covering:

```python
self.assertEqual(summary.evidence.grade, "limited")
self.assertEqual(summary.signal, "hold")
self.assertEqual(summary.evidence.classified_articles, 2)

self.assertEqual(strong.evidence.grade, "strong")
self.assertEqual(strong.signal, "buy")
self.assertAlmostEqual(strong.evidence.agreement, 1.0)

self.assertEqual(partial.evidence.classified_articles, 3)
self.assertAlmostEqual(partial.evidence.coverage, 0.6)
self.assertEqual(
    {driver.direction for driver in mixed.evidence.drivers},
    {"positive", "negative"},
)
```

Extend the OpenAI contract test so returned model rows are classified and synthesized missing rows are not. Extend CLI JSON and local UI payload assertions to require `evidence.grade`, `evidence.coverage`, `evidence.agreement`, classified/total counts, and drivers.

- [ ] **Step 2: Run the Python suite and verify the new contract fails**

Run: `python3 -m unittest discover -s tests -p "test_*.py"`

Expected: FAIL because the Python evidence types and fields do not exist.

- [ ] **Step 3: Add Python evidence dataclasses and provenance**

In `types.py`, add frozen `EvidenceDriver` and `EvidenceProfile` dataclasses mirroring the TypeScript JSON keys. Add `classified: bool = True` to `ArticleSentiment` and serialize it. Add `evidence: EvidenceProfile` to `SentimentSummary` and serialize it under the `evidence` key.

Use an immutable empty profile factory for legacy fixture construction:

```python
def empty_evidence_profile() -> EvidenceProfile:
    return EvidenceProfile(
        grade="limited",
        coverage=0.0,
        agreement=0.0,
        classified_articles=0,
        total_articles=0,
        drivers=(),
    )
```

Every normal parsed or cached result is classified. Both missing-row fallback construction sites in `sentiment.py` set `classified=False`.

- [ ] **Step 4: Implement exact scoring parity**

In `summarize_sentiment`, compute evidence with the same thresholds, impact equation, deterministic `article_id` tie-break, counter-direction inclusion, and 3-driver cap as the TypeScript engine. Set `articles_analyzed` to the classified count. Pass evidence grade and agreement into `_signal_from_score` and return `hold` when either gate fails.

Driver serialization must be:

```python
{
    "article_id": driver.article_id,
    "title": driver.title,
    "url": driver.url,
    "source": driver.source,
    "published_at": driver.published_at.isoformat() if driver.published_at else None,
    "direction": driver.direction,
    "impact": driver.impact,
    "confidence": driver.confidence,
    "reason": driver.reason,
}
```

- [ ] **Step 5: Surface evidence without adding CLI concepts**

Update the default text line to say `bullish`, `bearish`, or `no edge` while preserving JSON `signal` values. Append exactly `evidence <grade>, coverage <percent>, agreement <percent>` to the text summary. Keep verbose article rows unchanged except that synthesized rows remain clearly zero-confidence.

In `_build_response_payload`, add `classified` to each article and add a sibling `evidence` object beside `summary`. In the embedded local UI, add Evidence, Coverage, and Agreement metrics to the existing summary grid. The full article list already supplies driver details, so do not create a second local-UI driver list.

- [ ] **Step 6: Update the product contract documentation**

Replace the README overview sentence with:

```markdown
Recent equity news distilled into an evidence-backed near-term decision brief. Every result shows coverage, agreement, and the headlines driving the conclusion.
```

Document that `buy`, `sell`, and `hold` remain stable machine-readable values while the UI renders `Bullish`, `Bearish`, and `No edge`. State that limited evidence always returns `hold` and that the system makes no extra AI call for the decision brief.

- [ ] **Step 7: Run full repository verification**

Run: `python3 -m unittest discover -s tests -p "test_*.py"`

Expected: all Python tests PASS.

Run: `npm test`

Expected: all web tests PASS.

Run: `npm run build`

Expected: production build and type checking PASS.

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 8: Commit Python parity and docs**

```bash
git add stock_sentiment/types.py stock_sentiment/sentiment.py stock_sentiment/cli.py stock_sentiment/ui.py tests/test_sentiment_summary.py tests/test_sentiment_openai_contract.py tests/test_cli.py tests/test_ui.py README.md
git commit -m "Align every surface on evidence quality"
```
