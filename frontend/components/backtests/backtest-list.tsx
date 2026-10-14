"use client";

/**
 * Backtest history (Phase 11G §P2.5).
 *
 * Reads `GET /api/backtests/` (owner-scoped server-side, Phase 11F). Every
 * figure is a recorded metric from the run — `null` is rendered as "—" and is
 * never replaced with a guessed value. Runs recorded without an owner are not
 * returned by the backend at all.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatUtc } from "@/lib/format";
import type { BacktestRun, BacktestRunsResponse } from "@/lib/types";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

function pct(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function num(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

function signed(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

export function BacktestList() {
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<BacktestRunsResponse>("/api/backtests/");
      setRuns(res.runs);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState label="Loading backtest history…" />;
  if (error) return <ErrorState error={error} label="Backtest history unavailable" onRetry={() => void load()} />;
  if (runs.length === 0) {
    return (
      <EmptyState
        title="No backtest runs yet"
        hint="Recorded runs you own will appear here. A run with no owner is never surfaced."
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-zinc-800 bg-[#0c1118]" data-testid="backtest-list">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-500">
            <th className="px-3 py-2 font-medium">Created (UTC)</th>
            <th className="px-3 py-2 font-medium">Symbol</th>
            <th className="px-3 py-2 font-medium">TF</th>
            <th className="px-3 py-2 font-medium text-right">Trades</th>
            <th className="px-3 py-2 font-medium text-right">Win rate</th>
            <th className="px-3 py-2 font-medium text-right">Profit factor</th>
            <th className="px-3 py-2 font-medium text-right">Expectancy</th>
            <th className="px-3 py-2 font-medium text-right">Max DD</th>
            <th className="px-3 py-2 font-medium text-right">Net profit</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id} className="border-b border-zinc-800/60 text-zinc-300" data-testid="backtest-row">
              <td className="whitespace-nowrap px-3 py-2 font-mono">{formatUtc(run.created_at)}</td>
              <td className="px-3 py-2 font-semibold">{run.symbol ?? "—"}</td>
              <td className="px-3 py-2">{run.timeframe ?? "—"}</td>
              <td className="px-3 py-2 text-right font-mono">{run.total_trades}</td>
              <td className="px-3 py-2 text-right font-mono">{pct(run.win_rate)}</td>
              <td className="px-3 py-2 text-right font-mono">{num(run.profit_factor)}</td>
              <td className="px-3 py-2 text-right font-mono">{signed(run.expectancy)}</td>
              <td className="px-3 py-2 text-right font-mono">{num(run.max_drawdown)}</td>
              <td className="px-3 py-2 text-right font-mono">{signed(run.net_profit)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
