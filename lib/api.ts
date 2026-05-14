import type { AnalysisResult, ApiErrorBody } from "./types";

const GENERIC_ERROR =
  "The analysis could not be completed. Check your connection and try again.";

export async function analyzeTicker(ticker: string): Promise<AnalysisResult> {
  let response: Response;
  try {
    response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    });
  } catch {
    throw new Error(GENERIC_ERROR);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error(
      response.ok
        ? "The analyzer returned an unreadable response. Try again in a moment."
        : GENERIC_ERROR,
    );
  }

  if (!response.ok) {
    const message = (payload as ApiErrorBody)?.error?.message;
    throw new Error(message && message.trim() ? message : GENERIC_ERROR);
  }

  return payload as AnalysisResult;
}
