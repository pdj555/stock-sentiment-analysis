import type { SentimentLabel, Signal, Tone } from "./types";

const MINUS = "−"; // proper minus sign

export function tone(value: Signal | SentimentLabel): Tone {
  if (value === "buy" || value === "positive") return "pos";
  if (value === "sell" || value === "negative") return "neg";
  return "neu";
}

export function formatScore(value: number): string {
  if (!Number.isFinite(value)) return "0.000";
  const magnitude = Math.abs(value).toFixed(3);
  if (value > 0) return `+${magnitude}`;
  if (value < 0) return `${MINUS}${magnitude}`;
  return "0.000";
}

export function formatConfidence(value: number): string {
  if (!Number.isFinite(value)) return "0%";
  return `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`;
}

export function formatTime(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export const SIGNAL_COPY: Record<Signal, { word: string; line: string }> = {
  buy: {
    word: "Buy",
    line: "Recent coverage leans clearly bullish.",
  },
  sell: {
    word: "Sell",
    line: "Recent coverage leans clearly bearish.",
  },
  hold: {
    word: "Hold",
    line: "Coverage is mixed, or conviction is still low.",
  },
};

export const LABEL_COPY: Record<SentimentLabel, string> = {
  positive: "Positive",
  negative: "Negative",
  neutral: "Neutral",
};
