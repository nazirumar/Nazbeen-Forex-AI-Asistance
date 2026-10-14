"use client";

/**
 * Analytics (Phase 11G §P2.5).
 *
 * Reads `GET /api/journal/performance/` — an honest aggregate over *recorded*
 * journal fields only (Phase 11F). A statistic the data cannot support is
 * `null` on the wire and is rendered as "—", never as 0. The sample sizes the
 * backend used are shown next to the figures, and export links stream the same
 * recorded rows through `GET /api/journal/export/?format=csv|json`.
 */

import { useCallback, useEffect, useState } from "react";
import { api, apiBlob } from "@/lib/api";
import type { JournalPerformance } from "@/lib/types";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

function pct(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function num(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg bg-zinc-900/60 p-3" data-testid="analytics-stat">
      <p className="text-[11px] text-zinc-500">{label}</p>
      <p className="mt-0.5 font-mono text-lg font-semibold text-cyan-300">{value}</p>
      {hint ? <p className="mt-0.5 text-[11px] text-zinc-500">{hint}</p> : null}
    </div>
  );
}

const OUTCOME_ORDER = ["WIN", "LOSS", "BE", "PENDING"] as const;

export function AnalyticsPanel() {
  const [data, setData] = useState<JournalPerformance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api<JournalPerformance>("/api/journal/performance/"));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const exportJournal = async (format: "csv" | "json") => {
    setExporting(format);
    setExportError(null);
    try {
      const blob = await apiBlob(`/api/journal/export/?format=${format}`);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = format === "csv" ? "journal_export.csv" : "journal_export.json";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err);
    } finally {
      setExporting(null);
    }
  };

  if (loading) return <LoadingState label="Loading journal analytics…" />;
  if (error) return <ErrorState error={error} label="Analytics unavailable" onRetry={() => void load()} />;
  if (!data) return null;

  return (
    <div className="flex flex-col gap-4" data-testid="analytics-panel">
      {data.total_entries === 0 ? (
        <EmptyState
          title="No journal entries yet"
          hint="Record entries first; statistics appear only for data you actually recorded."
        />
      ) : null}

      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-zinc-100">Recorded performance</h2>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void exportJournal("csv")}
              disabled={exporting !== null}
              data-testid="export-csv"
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-40"
            >
              {exporting === "csv" ? "Exporting…" : "Export CSV"}
            </button>
            <button
              type="button"
              onClick={() => void exportJournal("json")}
              disabled={exporting !== null}
              data-testid="export-json"
              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-40"
            >
              {exporting === "json" ? "Exporting…" : "Export JSON"}
            </button>
          </div>
        </header>

        <dl className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Win rate" value={pct(data.win_rate)} hint={`${data.closed} closed`} />
          <Stat label="Average R:R" value={num(data.average_rr)} hint={`n=${data.rr_sample}`} />
          <Stat label="Total P&L" value={num(data.total_pnl)} hint={`n=${data.pnl_sample}`} />
          <Stat label="Expectancy" value={num(data.expectancy)} hint="per recorded P&L" />
          <Stat label="Profit factor" value={num(data.profit_factor)} hint="gross win / gross loss" />
          <Stat label="Max drawdown" value={num(data.max_drawdown)} hint={`n=${data.pnl_sample}`} />
        </dl>

        <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-zinc-500">
          <span className="rounded bg-zinc-900/60 px-2 py-0.5">Total entries: {data.total_entries}</span>
          <span className="rounded bg-zinc-900/60 px-2 py-0.5">Open: {data.open}</span>
          {OUTCOME_ORDER.map((key) => (
            <span key={key} className="rounded bg-zinc-900/60 px-2 py-0.5" data-testid="outcome-count">
              {key}: {data.outcomes[key] ?? 0}
            </span>
          ))}
        </div>

        <p className="mt-3 text-[11px] text-zinc-500" data-testid="analytics-note">
          {data.note}
        </p>
      </section>

      {exportError != null && (
        <ErrorState error={exportError} label="Export failed" />
      )}
    </div>
  );
}
