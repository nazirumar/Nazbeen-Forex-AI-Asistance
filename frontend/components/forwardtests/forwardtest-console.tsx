"use client";

/**
 * Forward-test console (Phase 11G §9/§10) — start a *simulated* forward test,
 * step it forward one observation cycle at a time, and inspect recorded
 * decisions and outcomes against the forward-testing API.
 *
 * Honesty rules baked in:
 * - No live order controls exist anywhere (this platform is analysis-only); a
 *   forward test observes the deterministic engine and places no orders.
 * - Every observation is labelled **simulated**.
 * - A value the backend did not record arrives as `null` and renders "—"; it is
 *   never replaced with a guessed number.
 */

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { formatUtc } from "@/lib/format";
import type {
  ForwardTestObservation,
  ForwardTestObservationsResponse,
  ForwardTestRun,
  ForwardTestRunResponse,
} from "@/lib/types";
import { ErrorState } from "@/components/ui/states";

const FIELD =
  "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-100 outline-none transition focus:border-cyan-600";

function num(value: number | null | undefined, digits = 5): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

const STATUS_STYLE: Record<string, string> = {
  active: "bg-cyan-500/15 text-cyan-300",
  stopped: "bg-zinc-700/60 text-zinc-300",
  failed: "bg-red-500/15 text-red-300",
};

const OUTCOME_STYLE: Record<string, string> = {
  PENDING: "text-zinc-400",
  WIN: "text-emerald-300",
  LOSS: "text-red-300",
  BE: "text-zinc-300",
};

export function ForwardTestConsole() {
  const [symbol, setSymbol] = useState("EURUSD");
  const [timeframe, setTimeframe] = useState("M15");
  const [slPips, setSlPips] = useState("10");
  const [tpPips, setTpPips] = useState("20");
  const [count, setCount] = useState("300");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [run, setRun] = useState<ForwardTestRun | null>(null);
  const [observations, setObservations] = useState<ForwardTestObservation[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [journalMsg, setJournalMsg] = useState<string | null>(null);

  const loadObservations = useCallback(async (id: string) => {
    const res = await api<ForwardTestObservationsResponse>(
      `/api/forwardtests/runs/${id}/observations/`,
    );
    setObservations(res.observations);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setRun(null);
    setObservations([]);
    setJournalMsg(null);
    try {
      const res = await api<ForwardTestRunResponse>("/api/forwardtests/runs/", {
        method: "POST",
        body: {
          symbol,
          timeframe,
          sl_pips: Number(slPips),
          tp_pips: Number(tpPips),
          count: Number(count),
        },
      });
      setRun(res.run);
      await loadObservations(res.run.id);
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  const observe = async () => {
    if (!run) return;
    setBusy("observe");
    setError(null);
    try {
      const res = await api<ForwardTestRunResponse>(`/api/forwardtests/runs/${run.id}/observe/`, {
        method: "POST",
      });
      setRun(res.run);
      await loadObservations(run.id);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  const stop = async () => {
    if (!run) return;
    setBusy("stop");
    setError(null);
    try {
      const res = await api<ForwardTestRunResponse>(`/api/forwardtests/runs/${run.id}/stop/`, {
        method: "POST",
      });
      setRun(res.run);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  const journalize = async (obs: ForwardTestObservation) => {
    setBusy(`journal-${obs.id}`);
    setError(null);
    setJournalMsg(null);
    try {
      const res = await api<{ journal_entry_id: string; source: string }>(
        `/api/forwardtests/observations/${obs.id}/journal/`,
        { method: "POST" },
      );
      setJournalMsg(`Created journal entry (source: ${res.source}).`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-4" data-testid="forwardtest-console">
      <form
        onSubmit={(e) => void submit(e)}
        className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4"
        data-testid="ft-config-form"
      >
        <header className="mb-2">
          <h2 className="text-sm font-semibold text-zinc-100">Start a forward test</h2>
          <p className="text-xs text-zinc-500">
            Simulated forward testing only — the engine is observed on fetched candles and{" "}
            <span className="font-semibold text-amber-300">no orders are placed</span>.
          </p>
        </header>
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-5">
          <label className="text-xs text-zinc-400">
            Symbol
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              data-testid="ft-symbol"
              className={`${FIELD} mt-1`}
            />
          </label>
          <label className="text-xs text-zinc-400">
            Timeframe
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              data-testid="ft-timeframe"
              className={`${FIELD} mt-1`}
            >
              {["M1", "M5", "M15", "H1"].map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-zinc-400">
            Stop-loss (pips)
            <input
              value={slPips}
              onChange={(e) => setSlPips(e.target.value)}
              inputMode="decimal"
              data-testid="ft-sl"
              className={`${FIELD} mt-1`}
            />
          </label>
          <label className="text-xs text-zinc-400">
            Take-profit (pips)
            <input
              value={tpPips}
              onChange={(e) => setTpPips(e.target.value)}
              inputMode="decimal"
              data-testid="ft-tp"
              className={`${FIELD} mt-1`}
            />
          </label>
          <label className="text-xs text-zinc-400">
            Candles
            <input
              value={count}
              onChange={(e) => setCount(e.target.value)}
              inputMode="numeric"
              data-testid="ft-count"
              className={`${FIELD} mt-1`}
            />
          </label>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            data-testid="ft-start"
            className="rounded-lg bg-cyan-600 px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:opacity-40"
          >
            {submitting ? "Starting…" : "Start forward test"}
          </button>
        </div>
      </form>

      {error != null && <ErrorState error={error} label="Forward test request failed" />}

      {run && (
        <section
          className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4"
          data-testid="ft-result"
        >
          <header className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-zinc-100">
              {run.symbol} · {run.timeframe}
            </h2>
            <span
              className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${
                STATUS_STYLE[run.status] ?? "bg-zinc-700/60 text-zinc-300"
              }`}
              data-testid="ft-status"
            >
              {run.status}
            </span>
            <span
              className="rounded bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300"
              data-testid="ft-simulated"
            >
              simulated
            </span>
            {run.data_source && (
              <span
                className="rounded bg-zinc-900/60 px-2 py-0.5 text-[10px] text-zinc-400"
                data-testid="ft-source"
              >
                source: {run.data_source}
              </span>
            )}
            <span className="text-[11px] text-zinc-500" data-testid="ft-observed-bar">
              last bar: {run.last_observed_bar ? formatUtc(run.last_observed_bar) : "—"}
            </span>
            <div className="ml-auto flex gap-2">
              <button
                type="button"
                onClick={() => void observe()}
                disabled={busy !== null || run.status !== "active"}
                data-testid="ft-observe"
                className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-40"
              >
                {busy === "observe" ? "Observing…" : "Observe now"}
              </button>
              <button
                type="button"
                onClick={() => void stop()}
                disabled={busy !== null || run.status !== "active"}
                data-testid="ft-stop"
                className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-40"
              >
                {busy === "stop" ? "Stopping…" : "Stop"}
              </button>
            </div>
          </header>

          {run.status === "failed" && (
            <p
              className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-xs text-red-300"
              data-testid="ft-failed"
            >
              {run.error ?? "The forward test failed."}
            </p>
          )}

          {run.note && (
            <p className="mt-2 rounded-lg bg-amber-500/10 px-3 py-2 text-[11px] text-amber-300">
              {run.note}
            </p>
          )}

          <dl className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <div className="rounded-lg bg-zinc-900/60 p-3">
              <p className="text-[11px] text-zinc-500">Observations</p>
              <p className="mt-0.5 font-mono text-base font-semibold text-cyan-300" data-testid="ft-count-total">
                {run.observations_count}
              </p>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-3">
              <p className="text-[11px] text-zinc-500">Resolved (W/L)</p>
              <p className="mt-0.5 font-mono text-base font-semibold text-zinc-200">
                {run.outcomes.WIN ?? 0} / {run.outcomes.LOSS ?? 0}
              </p>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-3">
              <p className="text-[11px] text-zinc-500">Pending</p>
              <p className="mt-0.5 font-mono text-base font-semibold text-zinc-200">
                {run.outcomes.PENDING ?? 0}
              </p>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-3">
              <p className="text-[11px] text-zinc-500">Strategy</p>
              <p className="mt-0.5 truncate font-mono text-xs text-zinc-300" title={run.strategy_version}>
                {run.strategy_version || "—"}
              </p>
            </div>
          </dl>

          {journalMsg && (
            <p className="mt-2 text-[11px] text-emerald-300" data-testid="ft-journal-msg">
              {journalMsg}
            </p>
          )}

          <div className="mt-3 overflow-x-auto rounded-lg border border-zinc-800">
            <table className="w-full text-left text-xs" data-testid="ft-observations">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  <th className="px-2 py-1.5 font-medium">Bar (UTC)</th>
                  <th className="px-2 py-1.5 font-medium">Decision</th>
                  <th className="px-2 py-1.5 font-medium text-right">Entry</th>
                  <th className="px-2 py-1.5 font-medium text-right">SL</th>
                  <th className="px-2 py-1.5 font-medium text-right">TP</th>
                  <th className="px-2 py-1.5 font-medium text-right">R</th>
                  <th className="px-2 py-1.5 font-medium">Outcome</th>
                  <th className="px-2 py-1.5 font-medium">Journal</th>
                </tr>
              </thead>
              <tbody>
                {observations.length === 0 && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-2 py-3 text-center text-zinc-500"
                      data-testid="ft-no-obs"
                    >
                      No observations recorded yet. Use “Observe now” to step the engine forward.
                    </td>
                  </tr>
                )}
                {observations.map((o) => (
                  <tr
                    key={o.id}
                    className="border-b border-zinc-800/60 text-zinc-300"
                    data-testid="ft-obs-row"
                  >
                    <td className="whitespace-nowrap px-2 py-1.5 font-mono">
                      {o.bar_time ? formatUtc(o.bar_time) : "—"}
                    </td>
                    <td className="px-2 py-1.5 font-semibold">{o.decision}</td>
                    <td className="px-2 py-1.5 text-right font-mono">{num(o.entry)}</td>
                    <td className="px-2 py-1.5 text-right font-mono">{num(o.sl)}</td>
                    <td className="px-2 py-1.5 text-right font-mono">{num(o.tp)}</td>
                    <td className="px-2 py-1.5 text-right font-mono">{num(o.rr, 2)}</td>
                    <td className={`px-2 py-1.5 font-mono ${OUTCOME_STYLE[o.outcome] ?? ""}`}>
                      {o.outcome}
                      {o.outcome_r != null ? ` (${num(o.outcome_r, 2)}R)` : ""}
                    </td>
                    <td className="px-2 py-1.5">
                      <button
                        type="button"
                        onClick={() => void journalize(o)}
                        disabled={busy !== null}
                        data-testid="ft-journal"
                        className="rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-40"
                      >
                        {busy === `journal-${o.id}` ? "…" : "Journal"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-2 text-[11px] text-zinc-500">
            Simulated forward-test results. This platform records and evaluates evidence — it does
            not place orders.
          </p>
        </section>
      )}
    </div>
  );
}
