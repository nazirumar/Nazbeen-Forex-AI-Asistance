"use client";

/**
 * Multi-timeframe analysis panel (Phase 11D §6).
 *
 * Renders the backend's real `mtf` block: H1 context, M15 bias, M5 setup and
 * M1 entry confirmation, plus the real conflict list. `null` from the backend
 * means the timeframe's data was unavailable — shown as "Unavailable", never
 * silently converted to NEUTRAL.
 */

import type { Bias, MtfView, StructureResponse } from "@/lib/types";
import { DataSourceBadge, EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

const BIAS_STYLE: Record<Bias, { label: string; cls: string; dot: string }> = {
  BULLISH: { label: "Bullish", cls: "text-emerald-300", dot: "bg-emerald-400" },
  BEARISH: { label: "Bearish", cls: "text-red-300", dot: "bg-red-400" },
  NEUTRAL: { label: "Neutral", cls: "text-zinc-300", dot: "bg-zinc-400" },
};

const TF_CARDS: { key: "H1" | "M15" | "M5" | "M1"; title: string; subtitle: string }[] = [
  { key: "H1", title: "H1", subtitle: "Market context" },
  { key: "M15", title: "M15", subtitle: "Directional bias" },
  { key: "M5", title: "M5", subtitle: "Setup" },
  { key: "M1", title: "M1", subtitle: "Entry confirmation" },
];

function BiasCard({
  title,
  subtitle,
  value,
}: {
  title: string;
  subtitle: string;
  value: Bias | null;
}) {
  const unavailable = value === null;
  const style = unavailable ? null : BIAS_STYLE[value as Bias];
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-3" data-testid={`mtf-${title}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{title}</span>
        <span className="text-[10px] text-zinc-600">{subtitle}</span>
      </div>
      <div className={`mt-2 flex items-center gap-2 text-sm font-semibold ${style ? style.cls : "text-zinc-500"}`}>
        <span className={`h-2 w-2 rounded-full ${style ? style.dot : "bg-zinc-600"}`} aria-hidden />
        {unavailable ? "Unavailable" : style!.label}
      </div>
    </div>
  );
}

export function MtfPanel({
  data,
  loading,
  error,
  onRetry,
}: {
  data: StructureResponse | null;
  loading: boolean;
  error: unknown;
  onRetry?: () => void;
}) {
  if (loading) return <LoadingState label="Loading multi-timeframe analysis…" />;
  if (error) return <ErrorState error={error} label="Multi-timeframe analysis failed" onRetry={onRetry} />;
  if (!data) {
    return <EmptyState title="No multi-timeframe data" hint="Select a symbol and timeframe, then retry." />;
  }

  const mtf: MtfView = data.mtf;

  return (
    <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4" data-testid="mtf-panel">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">Multi-timeframe analysis</h2>
          <p className="text-xs text-zinc-500">
            Deterministic bias from the structure engine · last {data.count} bars of {data.symbol}
          </p>
        </div>
        <DataSourceBadge source={data.data_source} />
      </header>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {TF_CARDS.map((card) => (
          <BiasCard key={card.key} title={card.title} subtitle={card.subtitle} value={mtf[card.key]} />
        ))}
      </div>

      <div className="mt-3" data-testid="mtf-conflicts">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Timeframe conflicts
        </h3>
        {mtf.conflicts.length === 0 ? (
          <p className="mt-1 text-xs text-zinc-500">No conflicts between decisive timeframes.</p>
        ) : (
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {mtf.conflicts.map((conflict) => (
              <li
                key={conflict}
                className="rounded-md border border-amber-700/50 bg-amber-500/10 px-2 py-1 text-xs text-amber-300"
              >
                ⚠ {conflict}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
