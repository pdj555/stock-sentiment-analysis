"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import TickerInput from "./TickerInput";

type HeroStatus = "idle" | "loading" | "error";

interface HeroProps {
  ticker: string;
  activeTicker: string;
  status: HeroStatus;
  error: string | null;
  onTickerChange: (value: string) => void;
  onSubmit: (value: string) => void;
  onClearError: () => void;
}

const CHIPS = ["AAPL", "NVDA", "TSLA", "AMD"];

const LOADING_LINES = [
  "Gathering recent headlines",
  "Reading the coverage",
  "Scoring every story",
  "Distilling the signal",
];

function BrandMark() {
  return (
    <div className="brand">
      <span className="brand-dot" aria-hidden />
      Sentiment
    </div>
  );
}

export default function Hero({
  ticker,
  activeTicker,
  status,
  error,
  onTickerChange,
  onSubmit,
  onClearError,
}: HeroProps) {
  const loading = status === "loading";
  const [lineIndex, setLineIndex] = useState(0);

  useEffect(() => {
    if (!loading) {
      setLineIndex(0);
      return;
    }
    const id = window.setInterval(() => {
      setLineIndex((index) => (index + 1) % LOADING_LINES.length);
    }, 2000);
    return () => window.clearInterval(id);
  }, [loading]);

  return (
    <div className="hero">
      <BrandMark />

      <motion.div
        initial={{ opacity: 0, y: 22 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      >
        <span className="eyebrow">Market intelligence</span>
        <h1 className="display">
          Read the market
          <br />
          before it <em>moves</em>.
        </h1>
        <p className="lede">
          Type a ticker. We read every recent headline, score the sentiment
          with AI, and distill it into one clear signal.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 22 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
      >
        <TickerInput
          value={ticker}
          onChange={onTickerChange}
          onSubmit={onSubmit}
          loading={loading}
        />
      </motion.div>

      <motion.div
        className="chips"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.3 }}
      >
        <span className="chips-label">Try</span>
        {CHIPS.map((symbol) => (
          <button
            key={symbol}
            type="button"
            className="chip"
            disabled={loading}
            onClick={() => {
              onTickerChange(symbol);
              onSubmit(symbol);
            }}
          >
            {symbol}
          </button>
        ))}
      </motion.div>

      <AnimatePresence mode="wait">
        {loading && (
          <motion.div
            key="loading"
            className="status-panel"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="orb" aria-hidden />
            <div className="status-body">
              <AnimatePresence mode="wait">
                <motion.span
                  key={lineIndex}
                  className="status-text"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.3 }}
                >
                  {LOADING_LINES[lineIndex]}…
                </motion.span>
              </AnimatePresence>
              <span className="status-sub">
                Analyzing <strong>{activeTicker}</strong> — this usually takes a
                few seconds.
              </span>
            </div>
          </motion.div>
        )}

        {status === "error" && error && (
          <motion.div
            key="error"
            className="error-card"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          >
            <span className="error-title">
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
                <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" />
                <path
                  d="M8 5v3.5M8 10.6v.1"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
              Could not analyze
            </span>
            <p className="error-msg">{error}</p>
            <button
              type="button"
              className="error-retry"
              onClick={() => {
                if (activeTicker) {
                  onSubmit(activeTicker);
                } else {
                  onClearError();
                }
              }}
            >
              {activeTicker ? "Try again" : "Dismiss"}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <p className="disclaimer">For research only — not financial advice.</p>
    </div>
  );
}
