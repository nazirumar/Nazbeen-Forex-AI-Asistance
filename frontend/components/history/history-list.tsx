"use client";

/**
 * Analysis history list (Phase 11D §8 — save & reopen).
 *
 * Reads `GET /api/analysis/` (owner-scoped server-side). Rows link to the
 * reopen page which fetches the full analysis. Only real stored fields are
 * shown; no aggregate statistics are computed.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatUtc } from "@/lib/format";
import type { AnalysisSummary } from "@/lib/types";
import { DataSourceBadge, EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

interface ListResponse {
  analyses: AnalysisSummary[];
}

function DecisionTag({ decision }: { decision: AnalysisSummary["decision"] }) {
  if (!decision) return <span className="text-zinc-500">—</span>;
  const cls =
    decision === "BUY"
      ? "bg-emerald-500/15 text-emerald-300"
      : decision === "SELL"
        ? "bg-red-500/15 text-red-300"
        : "bg-zinc-700/60 text-zinc-300";
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${cls}`} data-testid="history-decision">
      {decision}
    </span>
  );
}

export function HistoryList() {
  const [rows, setRows] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<ListResponse>("/api/analysis/");
      setRows(res.analyses);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState label="Loading analysis history…" />;
  if (error) return <ErrorState error={error} label="History unavailable" onRetry={() => void load()} />;
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No saved analyses yet"
        hint="Run a screenshot analysis and it will appear here for reopening."
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-zinc-800 bg-[#0c1118]" data-testid="history-list">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-500">
            <th className="px-3 py-2 font-medium">Created (UTC)</th>
            <th className="px-3 py-2 font-medium">Symbol</th>
            <th className="px-3 py-2 font-medium">TF</th>
            <th className="px-3 py-2 font-medium">Decision</th>
            <th className="px-3 py-2 font-medium">Source</th>
            <th className="px-3 py-2 font-medium">Summary</th>
            <th className="px-3 py-2 font-medium" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-zinc-800/60 text-zinc-300" data-testid="history-row">
              <td className="whitespace-nowrap px-3 py-2 font-mono">{formatUtc(row.created_at)}</td>
              <td className="px-3 py-2 font-semibold">{row.symbol ?? "—"}</td>
              <td className="px-3 py-2">{row.timeframe ?? "—"}</td>
              <td className="px-3 py-2">
                <DecisionTag decision={row.decision} />
              </td>
              <td className="px-3 py-2">
                <DataSourceBadge source={row.data_source} />
              </td>
              <td className="max-w-[36ch] truncate px-3 py-2" title={row.summary}>
                {row.summary || "—"}
              </td>
              <td className="px-3 py-2 text-right">
                <Link
                  href={`/dashboard/analysis/${row.id}`}
                  className="rounded border border-zinc-700 px-2 py-1 text-[11px] font-medium text-cyan-300 transition hover:bg-zinc-800"
                  data-testid="reopen-link"
                >
                  Reopen
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
