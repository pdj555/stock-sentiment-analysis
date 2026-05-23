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
        className={`verdict nous-panel tone-${signalTone}`}
        initial={{ opacity: 0, y: 24, scale: 0.99 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.7, ease: EASE }}
      >
        <span className="panel-legend">Signal analysis</span>
        <ScoreGauge score={summary.score} tone={signalTone} />

        <div className="verdict-main">
          <h3 className="signal-line">
            Signal:{" "}
            <span className="signal-word">{SIGNAL_COPY[summary.signal].word}</span>
          </h3>
          <p className="verdict-line">{SIGNAL_COPY[summary.signal].line}</p>
          <p className="metric-line">
            Label: {LABEL_COPY[summary.label]} · Confidence:{" "}
            {formatConfidence(summary.confidence)}
          </p>
        </div>
      </motion.section>

      <div className="stats-wrap">
        <span className="panel-legend">Metrics</span>
        <motion.div
          className={`stats-panel tone-${signalTone}`}
          variants={container}
          initial="hidden"
          animate="show"
        >
        <motion.div className={`stats-panel-item tone-${signalTone}`} variants={item}>
          <p className="stat-line">
            Score:{" "}
            <span className="stat-value tinted">{formatScore(summary.score)}</span>
          </p>
        </motion.div>
        <motion.div className="stats-panel-item" variants={item}>
          <p className="stat-line">
            Confidence:{" "}
            <span className="stat-value">{formatConfidence(summary.confidence)}</span>
          </p>
        </motion.div>
        <motion.div className="stats-panel-item" variants={item}>
          <p className="stat-line">
            Headlines:{" "}
            <span className="stat-value">{summary.articles_analyzed}</span>
          </p>
        </motion.div>
        <motion.div className="stats-panel-item" variants={item}>
          <p className="stat-line">
            Window:{" "}
            <span className="stat-value">{summary.lookback_days}d</span>
          </p>
        </motion.div>
        </motion.div>
      </div>

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
        <div className="articles-wrap">
          <span className="panel-legend">
            Headlines · <span className="articles-count-inline">{articles.length}</span>
          </span>
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
        </div>
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
