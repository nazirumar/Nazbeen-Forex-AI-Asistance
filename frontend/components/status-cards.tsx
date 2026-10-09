"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type BackendChecks = {
  database: string;
  cache: string;
  celery: string;
};

type FrontendChecks = { backend: string };

type BackendHealth = {
  status: string;
  checks: BackendChecks;
};

type FrontendHealth = {
  status: string;
  checks: FrontendChecks;
};

const CARD_TEMPLATES = [
  {
    id: "frontend",
    label: "Frontend",
    hint: "web server",
  },
  {
    id: "backend",
    label: "Backend",
    hint: "Django / DRF",
  },
  { id: "database", label: "Database", hint: "PostgreSQL" },
  { id: "redis", label: "Cache & broker", hint: "Redis" },
  { id: "celery", label: "Workers", hint: "Celery" },
] as const;

type CardId = (typeof CARD_TEMPLATES)[number]["id"];

const EMOJI_MAP: Record<string, string> = {
  ok: "●",
  degraded: "●",
  failed: "✕",
  unreachable: "○",
  unconfigured: "−",
  eager: "⟳",
};

export function StatusCards() {
  const [state, setState] = useState<Record<string, { ok: boolean; detail: string }>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      const results: Record<string, { ok: boolean; detail: string }> = {};
      // Frontend card: this Next.js app's own liveness probe (same origin).
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        const health = (await res.json()) as FrontendHealth;
        results.frontend = {
          ok: res.ok,
          detail: `${health.status} → backend ${health.checks.backend}`,
        };
      } catch (err) {
        const e = err as Error;
        results.frontend = { ok: false, detail: e.message };
      }
      // Backend/database/redis/celery cards: Django's health endpoint, called
      // directly (CORS is configured for the dev origin).
      try {
        const health = await api<BackendHealth>("/api/health/");
        const checks = health.checks;
        const summary = `${checks.database}/${checks.cache}/${checks.celery}`;
        results.backend = {
          ok: !["fail", "degraded"].includes(health.status),
          detail: summary,
        };
        results.database = {
          ok: checks.database === "ok",
          detail: checks.database,
        };
        results.redis = { ok: checks.cache === "ok", detail: checks.cache };
        results.celery = { ok: checks.celery === "ok", detail: checks.celery };
      } catch (err) {
        const e = err as Error;
        results.backend = { ok: false, detail: e.message };
      }
      setState(results);
      setLoading(false);
    })();
  }, []);

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {CARD_TEMPLATES.map((card) => (
        <div
          key={card.id}
          className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3"
        >
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">{card.label}</div>
            <div className="text-xs text-zinc-500">{card.hint}</div>
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-sm">
            <span
              className={`h-2 w-2 rounded-full ${state[card.id]?.ok ? "bg-emerald-400" : "bg-red-400"}`}
            />
            <span
              className={
                state[card.id]?.ok
                  ? "text-zinc-300"
                  : "text-red-300"
              }
            >
              {state[card.id]
                ? `${EMOJI_MAP[Boolean(state[card.id]?.ok) ? "ok" : "failed"]} ${state[card.id]?.detail}`
                : "—"}
            </span>
          </div>
        </div>
      ))}
      {loading ? (
        <div className="col-span-2 rounded-xl border border-zinc-800 bg-zinc-900/40 px-3 py-3 text-sm text-zinc-400">
          Connecting…
        </div>
      ) : null}
    </div>
  );
}
