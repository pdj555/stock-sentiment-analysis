import assert from "node:assert/strict";
import { test } from "node:test";
import {
  evidenceDirectionLabel,
  evidenceGradeLabel,
  SIGNAL_COPY,
} from "./format";

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

test("labels evidence drivers by absolute direction", () => {
  assert.equal(evidenceDirectionLabel("positive"), "Bullish");
  assert.equal(evidenceDirectionLabel("negative"), "Bearish");
});
