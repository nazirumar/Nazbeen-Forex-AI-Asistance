"use client";

/**
 * Auth session context (Phase 11D).
 *
 * Flow: login/register → DRF token persisted via `lib/api` → profile loaded
 * from `GET /api/auth/me/`. On mount the stored token is re-validated against
 * `/api/auth/me/` so a revoked or expired session lands the user on the login
 * screen instead of a half-rendered dashboard. A 401 from anywhere in the app
 * (see `AUTH_EXPIRED_EVENT`) clears the session and stores a reason that the
 * login page displays.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, AUTH_EXPIRED_EVENT, getToken, setToken } from "./api";
import type { AuthResponse, Me } from "./types";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

/** sessionStorage key describing why the login screen is showing. */
export const AUTH_REASON_KEY = "nazbeen_auth_reason";

export function getAuthReason(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(AUTH_REASON_KEY);
}

export function clearAuthReason(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(AUTH_REASON_KEY);
}

interface AuthContextValue {
  status: AuthStatus;
  user: Me | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<Me | null>(null);

  // Re-validate any stored session when the app boots.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!getToken()) {
        if (!cancelled) setStatus("anonymous");
        return;
      }
      try {
        const me = await api<Me>("/api/auth/me/");
        if (!cancelled) {
          setUser(me);
          setStatus("authenticated");
        }
      } catch {
        // 401 already cleared the token via the api helper; any other error
        // (backend unreachable) means we cannot confirm the session — treat
        // it as anonymous so nothing protected renders unverified.
        if (!cancelled) {
          setUser(null);
          setStatus("anonymous");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Session expiry anywhere in the app → anonymous + explain on login page.
  useEffect(() => {
    const onExpired = () => {
      // The api helper already cleared the token; clearing again guarantees a
      // stale token can never survive an expiry event (defense in depth).
      setToken(null);
      setUser(null);
      setStatus("anonymous");
      try {
        window.sessionStorage.setItem(AUTH_REASON_KEY, "expired");
      } catch {
        /* storage unavailable — login still works, just without the banner */
      }
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api<AuthResponse>("/api/auth/login/", {
      method: "POST",
      body: { username, password },
    });
    setToken(res.token);
    const me = await api<Me>("/api/auth/me/");
    setUser(me);
    setStatus("authenticated");
    clearAuthReason();
  }, []);

  const register = useCallback(async (username: string, email: string, password: string) => {
    const res = await api<AuthResponse>("/api/auth/register/", {
      method: "POST",
      body: { username, email, password },
    });
    setToken(res.token);
    const me = await api<Me>("/api/auth/me/");
    setUser(me);
    setStatus("authenticated");
    clearAuthReason();
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("/api/auth/logout/", { method: "POST" });
    } catch {
      // Best effort: the local session is cleared regardless, so a failed
      // server-side revoke never traps the user in a "logged-in" UI.
    } finally {
      setToken(null);
      setUser(null);
      setStatus("anonymous");
      clearAuthReason();
    }
  }, []);

  const value = useMemo(
    () => ({ status, user, login, register, logout }),
    [status, user, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
