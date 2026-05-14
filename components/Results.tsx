"use client";

import { motion } from "framer-motion";
import ArticleCard from "./ArticleCard";
import ScoreGauge from "./ScoreGauge";
import {
  formatConfidence,
  formatScore,
  formatTime,
  LABEL_COPY,
  SIGNAL_COPY,
  tone,
} from "@/lib/format";
import type { AnalysisResult } from "@/lib/types";

const EASE = [0.22, 1, 0.36, 1] as const;

const container = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.07, delayChildren: 0.08 },
  },
};

const item = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
};

interface ResultsProps {
  result: AnalysisResult;
  onReset: () => void;
}

export default function Results({ result, onReset }: ResultsProps) {
  const { summary, articles } = result;
  const signalTone = tone(summary.signal);
  const asOf = formatTime(summary.as_of);
  const warning =
    summary.classification_degraded && summary.classification_warnings.length > 0
      ? summary.classification_warnings.join(" ")
      : null;

  return (
    <div className="results">
      <header className="results-head">
        <h2 className="results-ticker">
          {summary.ticker}
          <span>
            {summary.source_label} · {summary.lookback_days}-day lookback
          </span>
        </h2>
        <button type="button" className="reset-btn" onClick={onReset}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
            <path
              d="M13 8a5 5 0 1 1-1.46-3.54M13 2v3h-3"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Analyze another
        </button>
      </header>

      <motion.section
        className={`verdict tone-${signalTone}`}
        initial={{ opacity: 0, y: 24, scale: 0.99 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.7, ease: EASE }}
      >
        <ScoreGauge score={summary.score} tone={signalTone} />

        <div className="verdict-main">
          <span className="verdict-eyebrow">Signal</span>
          <motion.h3
            className="signal-word"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.18, ease: EASE }}
          >
            {SIGNAL_COPY[summary.signal].word}
          </motion.h3>
          <p className="verdict-line">{SIGNAL_COPY[summary.signal].line}</p>
          <span className="label-pill">
            <span className="dot" aria-hidden />
            {LABEL_COPY[summary.label]} sentiment ·{" "}
            {formatConfidence(summary.confidence)} confidence
          </span>
        </div>
      </motion.section>

      <motion.div
        className="stats"
        variants={container}
        initial="hidden"
        animate="show"
      >
        <motion.div className={`stat tone-${signalTone}`} variants={item}>
          <span className="stat-label">Score</span>
          <span className="stat-value tinted">{formatScore(summary.score)}</span>
          <span className="stat-sub">weighted mean, −1 to +1</span>
        </motion.div>
        <motion.div className="stat" variants={item}>
          <span className="stat-label">Confidence</span>
          <span className="stat-value">
            {formatConfidence(summary.confidence)}
          </span>
          <span className="stat-sub">model conviction</span>
        </motion.div>
        <motion.div className="stat" variants={item}>
          <span className="stat-label">Headlines</span>
          <span className="stat-value">{summary.articles_analyzed}</span>
          <span className="stat-sub">stories analyzed</span>
        </motion.div>
        <motion.div className="stat" variants={item}>
          <span className="stat-label">Window</span>
          <span className="stat-value">{summary.lookback_days}d</span>
          <span className="stat-sub">news lookback</span>
        </motion.div>
      </motion.div>

      {warning && (
        <motion.div
          className="warning"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2, ease: EASE }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
            <path
              d="M8 1.6 15 14H1L8 1.6Z"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinejoin="round"
            />
            <path
              d="M8 6v3.4M8 11.4v.1"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          <span>{warning}</span>
        </motion.div>
      )}

      {articles.length > 0 && (
        <section>
          <div className="articles-head">
            <h3>The headlines</h3>
            <span className="articles-count">{articles.length}</span>
          </div>
          <motion.ul
            className="articles"
            variants={container}
            initial="hidden"
            animate="show"
          >
            {articles.map((article) => (
              <ArticleCard key={article.article_id} article={article} />
            ))}
          </motion.ul>
        </section>
      )}

      <footer className="results-footer">
        <span>{summary.source_label}</span>
        <span className="sep" aria-hidden />
        <span>{summary.lookback_days}-day lookback</span>
        {asOf && (
          <>
            <span className="sep" aria-hidden />
            <span>as of {asOf}</span>
          </>
        )}
        <span className="sep" aria-hidden />
        <span>Not financial advice.</span>
      </footer>
    </div>
  );
}
