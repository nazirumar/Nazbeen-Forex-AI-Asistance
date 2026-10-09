/** Token-authenticated API helper for the dashboard shell. */

const TOKEN_KEY = "nazbeen_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    window.localStorage.setItem(TOKEN_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_KEY);
  }
}

/**
 * Base URL of the Django backend.
 *
 * The frontend talks to Django directly (CORS is configured on the backend for
 * the dev origin), rather than through a Next.js same-origin proxy — the proxy
 * was tried in Phase 1 and Next's rewrite engine normalizes (strips) trailing
 * slashes, which breaks Django's APPEND_SLASH routing for POSTs.
 *
 * NEXT_PUBLIC_* values are inlined into client bundles by Next at dev/build
 * time, so both the client components and the API helper see the same URL.
 */
export function apiBase(): string {
  return process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Call a backend endpoint. Paths are resolved against the backend base URL. */
export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Token ${token}`;

  const url = path.startsWith("http") ? path : `${apiBase()}${path}`;

  const res = await fetch(url, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const detail =
      (data && (data.detail || JSON.stringify(data))) || `HTTP ${res.status}`;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}