"use client";

/**
 * Login screen (Phase 11D §2).
 *
 * Repaired token flow: the token returned by `POST /api/auth/login/` is
 * persisted immediately, then the profile is fetched with it. Errors from the
 * backend (invalid credentials, throttling, unreachable server) are surfaced
 * verbatim; an expired session is announced via a banner.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { clearAuthReason, getAuthReason, useAuth } from "@/lib/auth";

function LoginForm() {
  const { status, login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [expiredBanner, setExpiredBanner] = useState(false);

  useEffect(() => {
    // Banner either from the in-app expiry event (sessionStorage) or the
    // redirect query param set by the protected shell.
    if (getAuthReason() === "expired" || params.get("reason") === "expired") {
      setExpiredBanner(true);
      clearAuthReason();
    }
  }, [params]);

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
  }, [status, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const field =
    "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-cyan-600";

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0a0e14] p-4">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-[#0c1118] p-6">
        <div className="mb-5 flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-700 font-mono text-sm font-bold">
            N
          </span>
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Sign in</h1>
            <p className="text-xs text-zinc-500">Nazbeen Forex AI Asistance — analysis only</p>
          </div>
        </div>

        {expiredBanner && (
          <div
            role="status"
            className="mb-4 rounded-lg border border-amber-700/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-300"
            data-testid="session-expired-banner"
          >
            Your session expired — please sign in again.
          </div>
        )}

        <form onSubmit={submit} className="flex flex-col gap-3" data-testid="login-form">
          <label className="text-xs text-zinc-400">
            Username
            <input
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={`${field} mt-1`}
              data-testid="login-username"
            />
          </label>
          <label className="text-xs text-zinc-400">
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${field} mt-1`}
              data-testid="login-password"
            />
          </label>

          {error != null && (
            <div
              role="alert"
              className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-xs text-red-300"
              data-testid="login-error"
            >
              {error instanceof ApiError
                ? error.status === 429
                  ? `Too many attempts. ${error.message}`
                  : error.message
                : "Could not reach the server — is the backend running?"}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            data-testid="login-submit"
            className="mt-1 w-full rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-zinc-500">
          No account?{" "}
          <Link href="/register" className="text-cyan-400 underline-offset-2 hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
