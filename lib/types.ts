export type Signal = "buy" | "sell" | "hold";
export type SentimentLabel = "positive" | "negative" | "neutral";
export type Tone = "pos" | "neg" | "neu";
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

export interface AnalysisSummary {
  ticker: string;
  signal: Signal;
  label: SentimentLabel;
  score: number;
  confidence: number;
  articles_analyzed: number;
  classification_degraded: boolean;
  classification_warnings: string[];
  as_of: string;
  source: string;
  source_label: string;
  lookback_days: number;
  article_cap: number;
}

export interface AnalysisArticle {
  article_id: string;
  title: string;
  description: string | null;
  url: string | null;
  source: string | null;
  published_at: string | null;
  label: SentimentLabel;
  score: number;
  confidence: number;
  reason: string | null;
  classified: boolean;
}

export interface AnalysisResult {
  summary: AnalysisSummary;
  evidence: EvidenceProfile;
  articles: AnalysisArticle[];
}

export interface ApiErrorBody {
  error?: { message?: string };
}
