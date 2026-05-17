/**
 * Canonical site URL for metadata, sitemap, and robots.
 *
 * Resolution order:
 *   1. NEXT_PUBLIC_SITE_URL — set this in Vercel for the apex/custom domain.
 *   2. VERCEL_PROJECT_PRODUCTION_URL — Vercel-injected production hostname.
 *   3. VERCEL_URL — Vercel-injected per-deployment hostname (previews).
 *   4. http://localhost:3000 — local dev fallback.
 */
export function siteUrl(): URL {
  const explicit = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (explicit) return new URL(explicit);

  const prod = process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim();
  if (prod) return new URL(`https://${prod}`);

  const vercel = process.env.VERCEL_URL?.trim();
  if (vercel) return new URL(`https://${vercel}`);

  return new URL("http://localhost:3000");
}
