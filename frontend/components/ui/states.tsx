"use client";

/**
 * Shared loading / empty / error states (Phase 11D §3).
 *
 * Every data panel renders one of these instead of a blank area, and errors
 * always surface the real backend message (never a fabricated fallback).
 */

import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-8 text-sm text-zinc-400"
      data-testid="loading-state"
    >
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
      {label}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children?: ReactNode;
}) {
  return (
    <div
      className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/30 px-4 py-8 text-center"
      data-testid="empty-state"
    >
      <p className="text-sm font-medium text-zinc-300">{title}</p>
      {hint ? <p className="mt-1 text-xs text-zinc-500">{hint}</p> : null}
      {children}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  label = "Something went wrong",
}: {
  error: unknown;
  onRetry?: () => void;
  label?: string;
}) {
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : typeof error === "string"
          ? error
          : "Unexpected error";
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-900/60 bg-red-950/30 px-4 py-4"
      data-testid="error-state"
    >
      <p className="text-sm font-medium text-red-300">{label}</p>
      <p className="mt-1 break-words text-xs text-red-400/90">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-lg border border-red-800 px-3 py-1.5 text-xs font-medium text-red-200 transition hover:bg-red-900/40"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

/** Pill label for the backend's mock/real data source (never hidden). */
export function DataSourceBadge({ source }: { source: string | null | undefined }) {
  if (!source) return null;
  const isMock = source === "mock";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        isMock ? "bg-amber-500/15 text-amber-300" : "bg-cyan-500/15 text-cyan-300"
      }`}
      data-testid="data-source-badge"
    >
      {isMock ? "Mock data" : source === "mt5" ? "MT5 data" : "Live data"}
    </span>
  );
}
