import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

/**
 * GET /api/health — frontend liveness + backend reachability.
 * This route handler takes precedence over the /api/* proxy rewrite.
 */
export async function GET() {
  let backend: string = "unreachable";
  try {
    const res = await fetch(`${BACKEND_URL}/api/health/`, {
      cache: "no-store",
      // Next dev adds ~3s of fetch overhead per server-side call; keep the
      // probe budget generous so only real outages are reported.
      signal: AbortSignal.timeout(10000),
    });
    backend = res.ok ? "ok" : "degraded";
  } catch {
    backend = "unreachable";
  }

  const payload = {
    status: "ok",
    service: "nazbeen-forex-ai-frontend",
    version: process.env.npm_package_version ?? "0.1.0",
    time: new Date().toISOString(),
    checks: { backend },
  };
  return NextResponse.json(payload);
}
