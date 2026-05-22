import { checkBotId } from "botid/server";
import { NextResponse } from "next/server";
import { analyze } from "@/lib/server/analysis";
import { ConfigError, UpstreamError } from "@/lib/server/errors";
import { clientKey, rateLimit } from "@/lib/server/rate-limit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

function errorResponse(
  message: string,
  status: number,
  extraHeaders: Record<string, string> = {},
) {
  return NextResponse.json(
    { error: { message } },
    {
      status,
      headers: { "cache-control": "no-store", ...extraHeaders },
    },
  );
}

export async function POST(request: Request) {
  const limit = rateLimit(clientKey(request));
  if (!limit.allowed) {
    return errorResponse(
      "Too many requests. Try again in a moment.",
      429,
      { "retry-after": String(limit.retryAfterSeconds) },
    );
  }

  const verification = await checkBotId();
  if (verification.isBot) {
    return errorResponse("Access denied.", 403);
  }

  let ticker: unknown;
  try {
    const body = await request.json();
    ticker = (body as { ticker?: unknown } | null)?.ticker;
  } catch {
    return errorResponse(
      'The request body must be JSON, like {"ticker":"TSLA"}.',
      400,
    );
  }

  if (typeof ticker !== "string") {
    return errorResponse('The "ticker" field must be a string, like "TSLA".', 400);
  }

  try {
    const result = await analyze(ticker);
    return NextResponse.json(result, {
      headers: { "cache-control": "no-store" },
    });
  } catch (error) {
    if (error instanceof ConfigError) {
      return errorResponse(error.message, error.status);
    }
    if (error instanceof UpstreamError) {
      return errorResponse(error.message, error.status);
    }
    console.error("[analyze] unexpected failure", error);
    return errorResponse(
      "The analysis failed unexpectedly. Try again in a moment.",
      500,
    );
  }
}
