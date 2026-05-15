"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useState } from "react";
import Hero from "./Hero";
import Results from "./Results";
import { analyzeTicker } from "@/lib/api";
import type { AnalysisResult } from "@/lib/types";

type Status = "idle" | "loading" | "done" | "error";

const EASE = [0.22, 1, 0.36, 1] as const;

export default function Analyzer() {
  const [status, setStatus] = useState<Status>("idle");
  const [ticker, setTicker] = useState("");
  const [activeTicker, setActiveTicker] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (raw: string) => {
    const symbol = raw.trim().toUpperCase();
    if (!symbol) {
      setActiveTicker("");
      setError("Enter a ticker symbol to begin.");
      setStatus("error");
      return;
    }

    setActiveTicker(symbol);
    setError(null);
    setStatus("loading");

    try {
      const analysis = await analyzeTicker(symbol);
      setResult(analysis);
      setStatus("done");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Something went wrong. Try again in a moment.",
      );
      setStatus("error");
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setResult(null);
    setError(null);
    setTicker("");
    setActiveTicker("");
  }, []);

  const clearError = useCallback(() => {
    setError(null);
    setStatus("idle");
  }, []);

  return (
    <main className="shell">
      <AnimatePresence mode="wait">
        {status === "done" && result ? (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 26 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.55, ease: EASE }}
          >
            <Results result={result} onReset={reset} />
          </motion.div>
        ) : (
          <motion.div
            key="hero"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, y: -24 }}
            transition={{ duration: 0.5, ease: EASE }}
            style={{ display: "flex", flex: 1 }}
          >
            <Hero
              ticker={ticker}
              activeTicker={activeTicker}
              status={status === "done" ? "idle" : status}
              error={error}
              onTickerChange={setTicker}
              onSubmit={run}
              onClearError={clearError}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
