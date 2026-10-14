"use client";

/**
 * Backtest console (Phase 11G §7) — configure, run and inspect a *simulated*
 * historical backtest against the Phase 11G execution API.
 *
 * Honesty rules baked in:
 * - No live order controls exist anywhere (this platform is analysis-only).
 * - A metric the backend could not compute arrives as `null` and renders "—".
 * - Run progress shows a *status word* only — the backend exposes no measurable
 *   percentage, so no percentage is invented.
 * - Trades, metrics and the equity curve come from stored simulated results; a
 *   failed run shows its safe error message, never a fabricated result.
 */

import { useCallback, useState } from "react";
import { api, apiBlob } from "@/lib/api";
import { formatRatio, formatUtc } from "@/lib/format";
import type {
  BacktestMetrics,
  BacktestMetricsResponse,
  BacktestRun,
  BacktestRunResponse,
  BacktestTrade,
  BacktestTradesResponse,
  EquityPoint,
  EquityResponse,
} from "@/lib/types";
import { ErrorState } from "@/components/ui/states";

const FIELD =
  "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-100 outline-none transition focus:border-cyan-600";

function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function signed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg bg-zinc-900/60 p-3" data-testid="bt-metric">
      <p className="text-[11px] text-zinc-500">{label}</p>
      <p className="mt-0.5 font-mono text-base font-semibold text-cyan-300">{value}</p>
      {hint ? <p className="mt-0.5 text-[11px] text-zinc-500">{hint}</p> : null}
    </div>
  );
}

/** Inline SVG equity sparkline derived from the stored equity curve. */
export function EquitySparkline({ points }: { points: EquityPoint[] }) {
  if (points.length < 2) {
    return <p className="text-xs text-zinc-500" data-testid="bt-equity-empty">Equity curve unavailable.</p>;
  }
  const values = points.map((p) => p.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 100;
  const h = 40;
  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p.equity - min) / span) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="h-20 w-full"
      role="img"
      aria-label="Equity curve"
      data-testid="bt-equity"
    >
      <path d={path} fill="none" stroke="#22d3ee" strokeWidth="1" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

const STATUS_STYLE: Record<string, string> = {
  queued: "bg-zinc-700/60 text-zinc-300",
  running: "bg-cyan-500/15 text-cyan-300",
  completed: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-red-500/15 text-red-300",
};

export function BacktestConsole() {
  const [symbol, setSymbol] = useState("EURUSD");
  const [timeframe, setTimeframe] = useState("M15");
  const [count, setCount] = useState("500");
  const [initialBalance, setInitialBalance] = useState("10000");
  const [riskPct, setRiskPct] = useState("1");
  const [spreadPips, setSpreadPips] = useState("1");
  const [commissionPips, setCommissionPips] = useState("0.5");
  const [slippagePips, setSlippagePips] = useState("0.5");
  const [slPips, setSlPips] = useState("10");
  const [tpPips, setTpPips] = useState("20");
  const [walkForward, setWalkForward] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [run, setRun] = useState<BacktestRun | null>(null);
  const [metrics, setMetrics] = useState<BacktestMetrics | null>(null);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [selected, setSelected] = useState<BacktestTrade | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<unknown>(null);

  const loadResults = useCallback(async (id: string) => {
    const [m, tr, eq] = await Promise.all([
      api<BacktestMetricsResponse>(`/api/backtests/runs/${id}/metrics/`),
      api<BacktestTradesResponse>(`/api/backtests/runs/${id}/trades/`),
      api<EquityResponse>(`/api/backtests/runs/${id}/equity/`),
    ]);
    setMetrics(m.metrics);
    setTrades(tr.trades);
    setEquity(eq.points);
    setSelected(tr.trades[0] ?? null);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setRun(null);
    setMetrics(null);
    setTrades([]);
    setEquity([]);
    setSelected(null);
    try {
      const res = await api<BacktestRunResponse>("/api/backtests/runs/", {
        method: "POST",
        body: {
          symbol,
          timeframe,
          count: Number(count),
          initial_balance: Number(initialBalance),
          risk_pct: Number(riskPct),
          spread_pips: Number(spreadPips),
          commission_pips: Number(commissionPips),
          slippage_pips: Number(slippagePips),
          sl_pips: Number(slPips),
          tp_pips: Number(tpPips),
          walk_forward: walkForward,
        },
      });
      setRun(res.run);
      if (res.run.status === "completed") {
        await loadResults(res.run.id);
      }
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  const exportRun = async (format: "csv" | "json") => {
    if (!run) return;
    setExporting(format);
    setExportError(null);
    try {
      const blob = await apiBlob(`/api/backtests/runs/${run.id}/export/?format=${format}`);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `backtest-${run.id}.${format}`;
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

  const assumptions = metrics?.assumptions;

  return (
    <div className="flex flex-col gap-4" data-testid="backtest-console">
      <form
        onSubmit={(e) => void submit(e)}
        className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4"
        data-testid="bt-config-form"
      >
        <header className="mb-2">
          <h2 className="text-sm font-semibold text-zinc-100">Run a backtest</h2>
          <p className="text-xs text-zinc-500">
            Simulated historical evaluation only — no orders are placed. Costs and sizing are applied
            to every simulated trade.
          </p>
        </header>
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <label className="text-xs text-zinc-400">
            Symbol
            <input value={symbol} onChange={(e) => setSymbol(e.target.value)} data-testid="bt-symbol" className={`${FIELD} mt-1`} />
          </label>
          <label className="text-xs text-zinc-400">
            Timeframe
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} data-testid="bt-timeframe" className={`${FIELD} mt-1`}>
              {["M1", "M5", "M15", "H1"].map((tf) => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-zinc-400">
            Candles
            <input value={count} onChange={(e) => setCount(e.target.value)} inputMode="numeric" data-testid="bt-count" className={`${FIELD} mt-1`} />
          </label>
          <label className="text-xs text-zinc-400">
            Initial balance
            <input value={initialBalance} onChange={(e) => setInitialBalance(e.target.value)} inputMode="decimal" data-testid="bt-initial-balance" className={`${FIELD} mt-1`} />
          </label>
          <label className="text-xs text-zinc-400">
            Risk %
            <input value={riskPct} onChange={(e) => setRiskPct(e.target.value)} inputMode="decimal" data-testid="bt-risk" className={`${FIELD} mt-1`} />
          </label>
          <label className="text-xs text-zinc-400">
            Spread (pips)
            <input value={spreadPips} onChange={(e) => setSpreadPips(e.target.value)} inputMode="decimal" className={`${FIELD} mt-1`} />
          </label>
          <label className="text-xs text-zinc-400">
            Commission (pips)
            <input value={commissionPips} onChange={(e) => setCommissionPips(e.target.value)} inputMode="decimal" className={`${FIELD} mt-1`} />
          </label>
          <label className="text-xs text-zinc-400">
            Slippage (pips)
            <input value={slippagePips} onChange={(e) => setSlippagePips(e.target.value)} inputMode="decimal" className={`${FIELD} mt-1`} />
          </label>
          <label className="text-xs text-zinc-400">
            Stop-loss (pips)
            <input value={slPips} onChange={(e) => setSlPips(e.target.value)} inputMode="decimal" data-testid="bt-sl" className={`${FIELD} mt-1`} />
          </label>
          <label className="text-xs text-zinc-400">
            Take-profit (pips)
            <input value={tpPips} onChange={(e) => setTpPips(e.target.value)} inputMode="decimal" data-testid="bt-tp" className={`${FIELD} mt-1`} />
          </label>
          <label className="mt-5 flex items-center gap-2 text-xs text-zinc-400">
            <input type="checkbox" checked={walkForward} onChange={(e) => setWalkForward(e.target.checked)} data-testid="bt-walk-forward" />
            Walk-forward
          </label>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            data-testid="bt-start"
            className="rounded-lg bg-cyan-600 px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:opacity-40"
          >
            {submitting ? "Running…" : "Start backtest"}
          </button>
        </div>
      </form>

      {error != null && <ErrorState error={error} label="Backtest could not be started" />}

      {run && (
        <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4" data-testid="bt-result">
          <header className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-zinc-100">
              {run.symbol} · {run.timeframe}
            </h2>
            <span
              className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${STATUS_STYLE[run.status ?? ""] ?? "bg-zinc-700/60 text-zinc-300"}`}
              data-testid="bt-status"
            >
              {run.status ?? "unknown"}
            </span>
            {run.data_source && (
              <span className="rounded bg-zinc-900/60 px-2 py-0.5 text-[10px] text-zinc-400" data-testid="bt-source">
                source: {run.data_source}
              </span>
            )}
            {run.is_walk_forward && (
              <span className="rounded bg-cyan-500/15 px-2 py-0.5 text-[10px] text-cyan-300">walk-forward</span>
            )}
            <div className="ml-auto flex gap-2">
              <button type="button" onClick={() => void exportRun("csv")} disabled={exporting !== null} data-testid="bt-export-csv" className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-40">
                {exporting === "csv" ? "Exporting…" : "Export CSV"}
              </button>
              <button type="button" onClick={() => void exportRun("json")} disabled={exporting !== null} data-testid="bt-export-json" className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-40">
                {exporting === "json" ? "Exporting…" : "Export JSON"}
              </button>
            </div>
          </header>

          {run.status === "failed" && (
            <p className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-xs text-red-300" data-testid="bt-failed">
              {run.error ?? "The backtest failed."}
            </p>
          )}

          {run.note && (
            <p className="mt-2 rounded-lg bg-amber-500/10 px-3 py-2 text-[11px] text-amber-300" data-testid="bt-note">{run.note}</p>
          )}

          {metrics && (
            <>
              <dl className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
                <Stat label="Net profit" value={signed(metrics.net_profit)} hint={`n=${metrics.sample_size}`} />
                <Stat label="Win rate" value={pct(metrics.win_rate)} hint={`${metrics.wins}W / ${metrics.losses}L`} />
                <Stat label="Profit factor" value={num(metrics.profit_factor)} hint={metrics.profit_factor_note || "gross win / gross loss"} />
                <Stat label="Expectancy" value={signed(metrics.expectancy)} hint="per trade" />
                <Stat label="Average R" value={num(metrics.average_realized_r)} hint="realized multiple" />
                <Stat label="Max drawdown" value={num(metrics.max_drawdown)} hint={metrics.max_drawdown_pct != null ? `${metrics.max_drawdown_pct.toFixed(2)}%` : undefined} />
              </dl>

              {assumptions && (
                <p className="mt-2 text-[11px] text-zinc-500" data-testid="bt-assumptions">
                  Assumptions — spread {num(assumptions.spread_pips)} pips · commission {num(assumptions.commission_pips)} pips ·
                  slippage {num(assumptions.slippage_pips)} pips · SL {num(assumptions.sl_pips)} / TP {num(assumptions.tp_pips)} pips ·
                  sizing {num(assumptions.lots)} lots @ {num(assumptions.risk_pct)}% risk
                </p>
              )}

              <div className="mt-3 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                <p className="mb-1 text-[11px] text-zinc-500">Equity curve (simulated)</p>
                <EquitySparkline points={equity} />
              </div>

              <div className="mt-3 overflow-x-auto rounded-lg border border-zinc-800">
                <table className="w-full text-left text-xs" data-testid="bt-trades">
                  <thead>
                    <tr className="border-b border-zinc-800 text-zinc-500">
                      <th className="px-2 py-1.5 font-medium">#</th>
                      <th className="px-2 py-1.5 font-medium">Side</th>
                      <th className="px-2 py-1.5 font-medium">Entry (UTC)</th>
                      <th className="px-2 py-1.5 font-medium text-right">Entry</th>
                      <th className="px-2 py-1.5 font-medium text-right">Exit</th>
                      <th className="px-2 py-1.5 font-medium">Result</th>
                      <th className="px-2 py-1.5 font-medium text-right">P&L</th>
                      <th className="px-2 py-1.5 font-medium text-right">R</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.length === 0 && (
                      <tr>
                        <td colSpan={8} className="px-2 py-3 text-center text-zinc-500" data-testid="bt-no-trades">
                          No simulated trades were opened for this configuration.
                        </td>
                      </tr>
                    )}
                    {trades.map((t) => (
                      <tr
                        key={t.id}
                        onClick={() => setSelected(t)}
                        className={`cursor-pointer border-b border-zinc-800/60 text-zinc-300 ${selected?.id === t.id ? "bg-cyan-500/10" : "hover:bg-zinc-800/40"}`}
                        data-testid="bt-trade-row"
                      >
                        <td className="px-2 py-1.5 font-mono">{t.index}</td>
                        <td className="px-2 py-1.5">{t.side}</td>
                        <td className="whitespace-nowrap px-2 py-1.5 font-mono">{formatUtc(t.entry_time)}</td>
                        <td className="px-2 py-1.5 text-right font-mono">{t.entry.toFixed(5)}</td>
                        <td className="px-2 py-1.5 text-right font-mono">{t.exit_price != null ? t.exit_price.toFixed(5) : "—"}</td>
                        <td className="px-2 py-1.5">{t.result}</td>
                        <td className={`px-2 py-1.5 text-right font-mono ${t.pnl >= 0 ? "text-emerald-300" : "text-red-300"}`}>{signed(t.pnl)}</td>
                        <td className="px-2 py-1.5 text-right font-mono">{num(t.realized_r)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {selected && (
                <div className="mt-3 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3" data-testid="bt-trade-detail">
                  <p className="mb-1 text-[11px] font-semibold text-zinc-400">
                    Trade #{selected.index} — {selected.side} ({selected.result})
                  </p>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-zinc-400 sm:grid-cols-4">
                    <div>Entry time: <span className="font-mono text-zinc-200">{formatUtc(selected.entry_time)}</span></div>
                    <div>Exit time: <span className="font-mono text-zinc-200">{formatUtc(selected.exit_time)}</span></div>
                    <div>Entry: <span className="font-mono text-zinc-200">{selected.entry.toFixed(5)}</span></div>
                    <div>Exit: <span className="font-mono text-zinc-200">{selected.exit_price != null ? selected.exit_price.toFixed(5) : "—"}</span></div>
                    <div>Stop-loss: <span className="font-mono text-zinc-200">{selected.sl.toFixed(5)}</span></div>
                    <div>Take-profit: <span className="font-mono text-zinc-200">{selected.tp.toFixed(5)}</span></div>
                    <div>Lots: <span className="font-mono text-zinc-200">{formatRatio(selected.lots)}</span></div>
                    <div>Exit reason: <span className="font-mono text-zinc-200">{selected.exit_reason || "—"}</span></div>
                  </dl>
                  <p className="mt-2 text-[11px] text-zinc-500">
                    Simulated result. This platform records and evaluates evidence — it does not place orders.
                  </p>
                </div>
              )}
            </>
          )}

          {exportError != null && <div className="mt-3"><ErrorState error={exportError} label="Export failed" /></div>}
        </section>
      )}
    </div>
  );
}
