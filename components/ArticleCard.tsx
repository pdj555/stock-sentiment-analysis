"use client";

import { motion } from "framer-motion";
import { formatScore, formatTime, LABEL_COPY, tone } from "@/lib/format";
import type { AnalysisArticle } from "@/lib/types";

const itemVariants = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] as const },
  },
};

export default function ArticleCard({ article }: { article: AnalysisArticle }) {
  const articleTone = tone(article.label);
  const published = formatTime(article.published_at);
  const source = article.source?.trim() || "Unknown source";

  return (
    <motion.li className={`article tone-${articleTone}`} variants={itemVariants}>
      <span className="article-accent" aria-hidden />

      <div className="article-body">
        <h4 className="article-title">
          {article.url ? (
            <a href={article.url} target="_blank" rel="noreferrer noopener">
              {article.title || "Untitled article"}
            </a>
          ) : (
            article.title || "Untitled article"
          )}
        </h4>

        <div className="article-meta">
          <span className="src">{source}</span>
          {published && (
            <>
              <span className="sep" aria-hidden />
              <span>{published}</span>
            </>
          )}
          <span className="sep" aria-hidden />
          <span className="score">{formatScore(article.score)}</span>
        </div>

        {article.reason && <p className="article-reason">{article.reason}</p>}
      </div>

      <span className="article-badge">{LABEL_COPY[article.label]}</span>
    </motion.li>
  );
}
