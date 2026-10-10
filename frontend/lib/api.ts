/** Token-authenticated API helper for the dashboard (Phase 11D).
 *
 * Session model: the DRF token returned by `/api/auth/login/` or
 * `/api/auth/register/` is persisted in `localStorage` and attached to every
 * request as `Authorization: Token …`. It is cleared on explicit logout and
 * whenever the backend answers **401** for an authenticated call (session
 * expiry / revocation) — the `auth-expired` event lets the app redirect to the
 * login screen. Credentials and tokens are never logged or put in URLs.
 *
 * Rationale for localStorage (documented in PHASE_11D.md): the frontend and
 * backend are separate origins in development (`localhost:3000` →
 * `127.0.0.1:8000`) over plain HTTP, which rules out a `SameSite=None`
 * httpOnly cookie until HTTPS is deployed; every authenticated route remains
 * enforced server-side regardless of what the client stores.
 */

const TOKEN_KEY = "nazbeen_token";

/** Fired (on `window`) whenever a session ends unexpectedly (HTTP 401). */
export const AUTH_EXPIRED_EVENT = "nazbeen:auth-expired";

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
 * slashes, which breaks Django's APPEND_SLASH routing for POSTs to /api/auth/*.
 *
 * NEXT_PUBLIC_* values are inlined into client bundles by Next at dev/build
 * time, so both the client components and the API helper see the same URL.
 */
export function apiBase(): string {
  return process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";
}

export class ApiError extends Error {
  status: number;
  /** DRF field errors (`{field: [messages]}`) when the body carries them. */
  fields: Record<string, string[]> | null;

  constructor(status: number, message: string, fields: Record<string, string[]> | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

/** Endpoints whose 401 means "wrong credentials", not "session expired". */
function isCredentialPath(path: string): boolean {
  return path.startsWith("/api/auth/login") || path.startsWith("/api/auth/register");
}

function extractFields(data: unknown): Record<string, string[]> | null {
  if (!data || typeof data !== "object" || Array.isArray(data)) return null;
  const out: Record<string, string[]> = {};
  for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
    if (Array.isArray(value) && value.every((v) => typeof v === "string")) {
      out[key] = value as string[];
    } else if (key === "non_field_errors" && typeof value === "string") {
      out[key] = [value];
    }
  }
  return Object.keys(out).length ? out : null;
}

function extractMessage(status: number, data: unknown): string {
  if (data && typeof data === "object" && !Array.isArray(data)) {
    const d = data as Record<string, unknown>;
    let base: string | null = null;
    if (typeof d.detail === "string") base = d.detail;
    else if (typeof d.error === "string") base = d.error;
    // `details` (e.g. image-validator messages) belongs in the user-facing error.
    const details = Array.isArray(d.details)
      ? d.details.filter((v): v is string => typeof v === "string").join(" ")
      : null;
    if (base && details) return `${base}: ${details}`;
    if (base) return base;
    if (details) return details;
    const fields = extractFields(data);
    if (fields) {
      const first = Object.values(fields)[0];
      if (first && first.length) return first.join(" ");
    }
  }
  if (typeof data === "string" && data.trim()) return data;
  return `HTTP ${status}`;
}

function handleUnauthorized(path: string): void {
  if (typeof window === "undefined") return;
  if (isCredentialPath(path)) return; // 401 = bad credentials on these paths
  if (!getToken()) return; // nothing to expire
  setToken(null);
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
}

export interface ApiOptions {
  method?: string;
  body?: unknown;
  /** Multipart payload — the browser sets the boundary header itself. */
  formData?: FormData;
}

/** Call a backend endpoint. Paths are resolved against the backend base URL. */
export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (!options.formData) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Token ${token}`;

  const url = path.startsWith("http") ? path : `${apiBase()}${path}`;

  const res = await fetch(url, {
    method: options.method ?? "GET",
    headers,
    body: options.formData ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
    cache: "no-store",
  });

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null; // non-JSON body (e.g. an HTML error page) — never crash
    }
  }

  if (!res.ok) {
    if (res.status === 401) handleUnauthorized(path);
    throw new ApiError(res.status, extractMessage(res.status, data ?? text), extractFields(data));
  }
  return data as T;
}

/** Fetch a protected binary resource (e.g. a stored screenshot) as a Blob. */
export async function apiBlob(path: string): Promise<Blob> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Token ${token}`;
  const url = path.startsWith("http") ? path : `${apiBase()}${path}`;
  const res = await fetch(url, { headers, cache: "no-store" });
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized(path);
    let data: unknown = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    throw new ApiError(res.status, extractMessage(res.status, data), extractFields(data));
  }
  return res.blob();
}
