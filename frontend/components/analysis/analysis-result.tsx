"use client";

/**
 * Screenshot-analysis result view (Phase 11D §5).
 *
 * Renders the backend's structured output verbatim: AI vision observations,
 * deterministic ICT/SMC findings, evidence with its source, AI/deterministic
 * disagreements, the BUY SCENARIO / SELL SCENARIO / WAIT verdict, uncertainty
 * and unavailable data. Nothing is recomputed or embellished client-side.
 */

import { formatUtc } from "@/lib/format";
import type { AnalysisResult, DisagreementItem, EvidenceItem } from "@/lib/types";
import { DataSourceBadge } from "@/components/ui/states";

function DecisionBadge({ decision }: { decision: string }) {
  const style =
    decision === "BUY"
      ? "border-emerald-700/60 bg-emerald-500/10 text-emerald-300"
      : decision === "SELL"
        ? "border-red-700/60 bg-red-500/10 text-red-300"
        : "border-zinc-700 bg-zinc-800/70 text-zinc-300";
  const label = decision === "BUY" ? "BUY SCENARIO" : decision === "SELL" ? "SELL SCENARIO" : "WAIT";
  return (
    <span
      data-testid="decision-badge"
      className={`rounded-lg border px-3 py-1.5 text-sm font-bold tracking-wide ${style}`}
    >
      {label}
    </span>
  );
}

function EvidenceRow({ item, index }: { item: EvidenceItem; index: number }) {
  return (
    <li className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-2.5" data-testid="evidence-item">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px] uppercase text-zinc-400">
          {item.type}
        </span>
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
            item.source === "deterministic"
              ? "bg-cyan-500/15 text-cyan-300"
              : "bg-violet-500/15 text-violet-300"
          }`}
        >
          {item.source}
        </span>
        {typeof item.price_level === "number" && (
          <span className="font-mono text-[11px] text-zinc-400">{item.price_level.toFixed(5)}</span>
        )}
        {typeof item.confidence === "number" && (
          <span className="text-[11px] text-zinc-500">confidence {item.confidence.toFixed(2)}</span>
        )}
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-zinc-300">{item.description}</p>
      <p className="mt-1 text-[10px] text-zinc-600">
        {item.timestamp ? `at ${formatUtc(item.timestamp)} UTC` : "no timestamp"} · item {index + 1}
      </p>
    </li>
  );
}

function DisagreementRow({ item }: { item: DisagreementItem }) {
  return (
    <li className="rounded-lg border border-amber-800/50 bg-amber-950/20 p-2.5" data-testid="disagreement-item">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-amber-300">{item.aspect}</span>
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
            item.resolved ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
          }`}
        >
          {item.resolved ? "resolved by authority" : "open"}
        </span>
      </div>
      <div className="mt-1.5 grid gap-1 text-xs sm:grid-cols-2">
        <p className="text-zinc-300">
          <span className="text-zinc-500">Deterministic: </span>
          {JSON.stringify(item.deterministic)}
        </p>
        <p className="text-zinc-300">
          <span className="text-zinc-500">AI: </span>
          {JSON.stringify(item.ai)}
        </p>
      </div>
      <p className="mt-1 text-[11px] text-amber-400/90">{item.reason}</p>
    </li>
  );
}

export function AnalysisResultView({ result }: { result: AnalysisResult }) {
  const deterministicEntries = Object.entries(result.deterministic_signals ?? {});
  return (
    <article className="flex flex-col gap-4" data-testid="analysis-result">
      {/* Verdict */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <DecisionBadge decision={result.decision} />
            <span className="text-xs text-zinc-500">
              {result.symbol ?? "symbol not observed"} · {result.timeframe ?? "timeframe not observed"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                result.data_synchronized
                  ? "bg-emerald-500/15 text-emerald-300"
                  : "bg-zinc-700/60 text-zinc-300"
              }`}
              data-testid="sync-badge"
            >
              {result.data_synchronized ? "data synchronized" : "data not synchronized"}
            </span>
            <DataSourceBadge source={result.source} />
          </div>
        </header>

        <p className="text-sm leading-relaxed text-zinc-300">{result.summary}</p>

        <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
          <div className="rounded-lg bg-zinc-900/60 p-2">
            <dt className="text-zinc-500">Direction</dt>
            <dd className="mt-0.5 font-semibold capitalize text-zinc-200">{result.direction}</dd>
          </div>
          <div className="rounded-lg bg-zinc-900/60 p-2">
            <dt className="text-zinc-500">R:R</dt>
            <dd className="mt-0.5 font-mono font-semibold text-zinc-200">
              {typeof result.risk_reward === "number" ? result.risk_reward.toFixed(2) : "—"}
            </dd>
          </div>
          <div className="rounded-lg bg-zinc-900/60 p-2">
            <dt className="text-zinc-500">Analysis time</dt>
            <dd className="mt-0.5 font-mono text-zinc-200">{formatUtc(result.analysis_timestamp)}</dd>
          </div>
          <div className="rounded-lg bg-zinc-900/60 p-2">
            <dt className="text-zinc-500">Model</dt>
            <dd className="mt-0.5 truncate font-mono text-zinc-200">{result.model ?? "unavailable"}</dd>
          </div>
        </dl>

        {(result.entry_levels.length > 0 || result.sl !== null || result.tp !== null) && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs" data-testid="result-levels">
            {result.entry_levels.map((lvl, i) => (
              <span key={`e${i}`} className="rounded bg-cyan-500/10 px-2 py-1 font-mono text-cyan-300">
                Entry {lvl.toFixed(5)}
              </span>
            ))}
            {result.sl !== null && (
              <span className="rounded bg-red-500/10 px-2 py-1 font-mono text-red-300">
                SL {result.sl.toFixed(5)}
              </span>
            )}
            {result.tp !== null && (
              <span className="rounded bg-emerald-500/10 px-2 py-1 font-mono text-emerald-300">
                TP {result.tp.toFixed(5)}
              </span>
            )}
          </div>
        )}
      </section>

      {/* AI observations */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h3 className="text-sm font-semibold text-zinc-100">AI vision observations</h3>
        <p className="mt-0.5 text-xs text-zinc-500">
          Model <span className="font-mono">{result.model ?? "unavailable"}</span> — descriptive only,
          never authoritative over the deterministic engine.
        </p>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
          {result.ai_explanation || "No AI explanation was produced for this analysis."}
        </p>
      </section>

      {/* Deterministic findings */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h3 className="text-sm font-semibold text-zinc-100">Deterministic ICT/SMC findings</h3>
        {deterministicEntries.length === 0 ? (
          <p className="mt-2 text-xs text-zinc-500">No deterministic signals were produced.</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1.5 text-xs">
            {deterministicEntries.map(([key, value]) => (
              <li
                key={key}
                className="flex gap-2 rounded-lg border border-zinc-800 bg-zinc-900/40 px-2.5 py-2"
                data-testid="deterministic-signal"
              >
                <span className="shrink-0 font-mono uppercase text-cyan-400">{key}</span>
                <span className="break-words text-zinc-300">
                  {typeof value === "string" ? value : JSON.stringify(value)}
                </span>
              </li>
            ))}
          </ul>
        )}
        {result.mtf_conflicts.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {result.mtf_conflicts.map((c) => (
              <li
                key={c}
                className="rounded-md border border-amber-700/50 bg-amber-500/10 px-2 py-1 text-xs text-amber-300"
              >
                ⚠ {c}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Evidence */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h3 className="text-sm font-semibold text-zinc-100">Evidence ({result.evidence.length})</h3>
        {result.evidence.length === 0 ? (
          <p className="mt-2 text-xs text-zinc-500">No evidence items recorded.</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {result.evidence.map((item, i) => (
              <EvidenceRow key={`${item.type}-${i}`} item={item} index={i} />
            ))}
          </ul>
        )}
      </section>

      {/* Disagreements */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h3 className="text-sm font-semibold text-zinc-100">
          AI vs deterministic disagreements ({result.disagreements.length})
        </h3>
        {result.disagreements.length === 0 ? (
          <p className="mt-2 text-xs text-zinc-500">AI and deterministic analysis agreed.</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {result.disagreements.map((item, i) => (
              <DisagreementRow key={`${item.aspect}-${i}`} item={item} />
            ))}
          </ul>
        )}
      </section>

      {/* Uncertainty / unavailable */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h3 className="text-sm font-semibold text-zinc-100">Uncertainty &amp; unavailable data</h3>
        {result.uncertainty.length === 0 && result.errors.length === 0 ? (
          <p className="mt-2 text-xs text-zinc-500">Nothing flagged for this analysis.</p>
        ) : (
          <div className="mt-2 flex flex-col gap-2">
            {result.uncertainty.length > 0 && (
              <ul className="flex flex-col gap-1">
                {result.uncertainty.map((u) => (
                  <li key={u} className="text-xs text-amber-300/90" data-testid="uncertainty-item">
                    ▸ {u}
                  </li>
                ))}
              </ul>
            )}
            {result.errors.length > 0 && (
              <ul className="flex flex-col gap-1">
                {result.errors.map((e) => (
                  <li key={e} className="text-xs text-red-300/90" data-testid="analysis-error-item">
                    ▸ {e}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
    </article>
  );
}
