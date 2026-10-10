"use client";

/**
 * Registration screen (Phase 11D §2).
 *
 * Creates the account via `POST /api/auth/register/`, persists the returned
 * token and signs the user in. Django password-validation messages from the
 * serializer are rendered field-by-field, verbatim.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { status, register } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
  }, [status, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (password !== confirm) {
      setLocalError("Passwords do not match.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await register(username, email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const field =
    "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-cyan-600";

  const apiError = error instanceof ApiError ? error : null;
  const fieldError = (name: string): string | undefined => apiError?.fields?.[name]?.join(" ");
  const nonField = apiError?.fields?.["non_field_errors"]?.join(" ") ?? null;

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0a0e14] p-4">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-[#0c1118] p-6">
        <div className="mb-5 flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-700 font-mono text-sm font-bold">
            N
          </span>
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Create account</h1>
            <p className="text-xs text-zinc-500">Analysis-only Forex decision support</p>
          </div>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3" data-testid="register-form">
          <label className="text-xs text-zinc-400">
            Username
            <input
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={`${field} mt-1`}
              data-testid="register-username"
            />
            {fieldError("username") && (
              <span className="mt-1 block text-xs text-red-400" data-testid="register-username-error">
                {fieldError("username")}
              </span>
            )}
          </label>
          <label className="text-xs text-zinc-400">
            Email <span className="text-zinc-600">(optional)</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={`${field} mt-1`}
            />
            {fieldError("email") && (
              <span className="mt-1 block text-xs text-red-400">{fieldError("email")}</span>
            )}
          </label>
          <label className="text-xs text-zinc-400">
            Password
            <input
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${field} mt-1`}
              data-testid="register-password"
            />
            {fieldError("password") && (
              <span className="mt-1 block text-xs text-red-400" data-testid="register-password-error">
                {fieldError("password")}
              </span>
            )}
          </label>
          <label className="text-xs text-zinc-400">
            Confirm password
            <input
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className={`${field} mt-1`}
              data-testid="register-confirm"
            />
          </label>

          {(localError || nonField || (apiError && !Object.keys(apiError.fields ?? {}).length)) && (
            <div
              role="alert"
              className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-xs text-red-300"
              data-testid="register-error"
            >
              {localError ??
                nonField ??
                (apiError ? apiError.message : "Registration failed")}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            data-testid="register-submit"
            className="mt-1 w-full rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-zinc-500">
          Already registered?{" "}
          <Link href="/login" className="text-cyan-400 underline-offset-2 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
