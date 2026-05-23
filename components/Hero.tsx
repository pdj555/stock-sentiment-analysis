"use client";

import { AnimatePresence, motion } from "framer-motion";
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

  return (
    <div className="hero">
      <motion.section
        className="nous-panel hero-panel"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1 className="nous-title">Sentiment</h1>
        <p className="nous-section">Ticker query</p>

        <p className="hero-prompt">What ticker should we read?</p>

        <div className="hero-input">
          <TickerInput
            value={ticker}
            onChange={onTickerChange}
            onSubmit={onSubmit}
            loading={loading}
          />
        </div>

        <div className="chips">
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
        </div>

        <AnimatePresence mode="wait">
          {loading && (
            <motion.p
              key="loading"
              className="loading-line"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              loading...
            </motion.p>
          )}

          {status === "error" && error && (
            <motion.div
              key="error"
              className="error-card"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <span className="error-title">Error</span>
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
      </motion.section>

      <p className="disclaimer">for research only — not financial advice</p>
    </div>
  );
}
