import type { NextConfig } from "next";

/**
 * No rewrites: the frontend calls the Django backend directly (CORS is
 * configured on the backend for the dev origin). A Next.js same-origin rewrite
 * was tried during Phase 1, but Next's rewrite engine normalizes (strips)
 * trailing slashes before forwarding, which breaks Django's APPEND_SLASH
 * routing for POSTs to /api/auth/*. See frontend/lib/api.ts.
 *
 * The only /api/* route defined here is app/api/health/route.ts — the
 * frontend's own liveness probe.
 */
const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
};

export default nextConfig;