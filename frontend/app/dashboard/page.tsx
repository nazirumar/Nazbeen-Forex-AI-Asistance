"use client";

/**
 * Overview page (Phase 11D §3/§6): connection state and the real
 * multi-timeframe analysis, plus detected-structure counts taken verbatim
 * from the structure engine (honest numbers only — no decorative stats).
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { MtfPanel } from "@/components/analysis/mtf-panel";
import { useMarket } from "@/components/layout/market-context";
import { EmptyState, ErrorState, LoadingState, DataSourceBadge } from "@/components/ui/states";
import type { Mt5Status, StructureResponse } from "@/lib/types";

function ConnectionCard({ status, error }: { status: Mt5Status | null; error: boolean }) {
  if (error) {
    return <ErrorState error="Could not reach /api/mt5/status/" label="Connection status unavailable" />;
  }
  if (!status) return <LoadingState label="Loading connection status…" />;
  return (
    <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4" data-testid="connection-card">
      <header className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-zinc-100">Data connection</h2>
        <DataSourceBadge source={status.mode} />
      </header>
      <dl className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <div className="rounded-lg bg-zinc-900/60 p-2">
          <dt className="text-zinc-500">Status</dt>
          <dd className={`mt-0.5 font-semibold ${status.connected ? "text-emerald-300" : "text-red-300"}`}>
            {status.connected ? "Connected" : "Disconnected"}
          </dd>
        </div>
        <div className="rounded-lg bg-zinc-900/60 p-2">
          <dt className="text-zinc-500">Broker</dt>
          <dd className="mt-0.5 truncate font-mono text-zinc-100">{status.broker ?? "—"}</dd>
        </div>
        <div className="rounded-lg bg-zinc-900/60 p-2">
          <dt className="text-zinc-500">Server</dt>
          <dd className="mt-0.5 truncate font-mono text-zinc-100">{status.server ?? "—"}</dd>
        </div>
        <div className="rounded-lg bg-zinc-900/60 p-2">
          <dt className="text-zinc-500">Market</dt>
          <dd className="mt-0.5 font-semibold text-zinc-100">
            {status.market_state === "open" ? "Open" : status.market_state === "closed" ? "Closed" : "—"}
          </dd>
        </div>
      </dl>
      {status.mode === "mock" && (
        <p className="mt-2 text-xs text-amber-300/90">
          ⚠ Mock data source — prices are simulated and clearly labeled, not live market data.
        </p>
      )}
    </section>
  );
}

export default function OverviewPage() {
  const { symbol, timeframe } = useMarket();
  const [structure, setStructure] = useState<StructureResponse | null>(null);
  const [structureLoading, setStructureLoading] = useState(true);
  const [structureError, setStructureError] = useState<unknown>(null);

  const [status, setStatus] = useState<Mt5Status | null>(null);
  const [statusError, setStatusError] = useState(false);

  const loadStructure = useCallback(async () => {
    setStructureLoading(true);
    setStructureError(null);
    try {
      const res = await api<StructureResponse>(
        `/api/structure/?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&count=200`,
      );
      setStructure(res);
    } catch (err) {
      setStructureError(err);
      setStructure(null);
    } finally {
      setStructureLoading(false);
    }
  }, [symbol, timeframe]);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await api<Mt5Status>("/api/mt5/status/"));
      setStatusError(false);
    } catch {
      setStatus(null);
      setStatusError(true);
    }
  }, []);

  useEffect(() => {
    void loadStructure();
  }, [loadStructure]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const detections = structure
    ? [
        { label: "BOS/CHOCH/MSS events", value: structure.events.length },
        { label: "Fair value gaps", value: structure.fvgs.length },
        { label: "Order blocks", value: structure.order_blocks.length },
        { label: "Liquidity levels", value: structure.liquidity.length },
        { label: "Confirmed swings", value: structure.swings.length },
      ]
    : [];

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-base font-semibold text-zinc-100">Overview</h1>
          <p className="text-xs text-zinc-500">
            {symbol} · {timeframe} — analysis-only decision support, no trade execution
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void loadStructure();
            void loadStatus();
          }}
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800"
        >
          Refresh
        </button>
      </header>

      <ConnectionCard status={status} error={statusError} />

      <MtfPanel data={structure} loading={structureLoading} error={structureError} onRetry={() => void loadStructure()} />

      {structureLoading ? (
        <LoadingState label="Loading detected structures…" />
      ) : structureError ? (
        <ErrorState error={structureError} label="Structure data unavailable" onRetry={() => void loadStructure()} />
      ) : structure === null ? (
        <EmptyState title="No structure data" />
      ) : (
        <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4" data-testid="detections-card">
          <header className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-zinc-100">Detected market structures</h2>
            <DataSourceBadge source={structure.data_source} />
          </header>
          <p className="text-xs text-zinc-500">
            Deterministic engine output over the last {structure.count} {structure.timeframe} bars of{" "}
            {structure.symbol} — zero means none detected, not missing data.
          </p>
          <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
            {detections.map((d) => (
              <li key={d.label} className="rounded-lg bg-zinc-900/60 p-2.5">
                <p className="font-mono text-lg font-semibold text-cyan-300">{d.value}</p>
                <p className="mt-0.5 text-[11px] text-zinc-500">{d.label}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
