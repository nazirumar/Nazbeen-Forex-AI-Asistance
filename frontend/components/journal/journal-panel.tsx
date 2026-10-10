"use client";

/**
 * Journal + searchable history (Phase 11D §8).
 *
 * Reads the real `GET /api/journal/search/` and `POST /api/journal/entries/`
 * endpoints. All columns are recorded fields (symbol, timeframe, decision,
 * outcome, R:R, notes, created time) — no performance analytics are computed
 * or invented client-side.
 */

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatUtc } from "@/lib/format";
import type { JournalEntry } from "@/lib/types";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

interface SearchResponse {
  entries: JournalEntry[];
}

export function JournalPanel() {
  const [query, setQuery] = useState("");
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const [symbol, setSymbol] = useState("EURUSD");
  const [timeframe, setTimeframe] = useState("M15");
  const [decision, setDecision] = useState("");
  const [outcome, setOutcome] = useState("PENDING");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [saveOk, setSaveOk] = useState(false);

  const search = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<SearchResponse>(
        `/api/journal/search/?q=${encodeURIComponent(q)}`,
      );
      setEntries(res.entries);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void search("");
  }, [search]);

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    setSaveOk(false);
    try {
      await api("/api/journal/entries/", {
        method: "POST",
        body: {
          symbol,
          timeframe,
          scenario_decision: decision || null,
          outcome,
          notes,
        },
      });
      setNotes("");
      setSaveOk(true);
      await search(query);
    } catch (err) {
      setSaveError(err);
    } finally {
      setSaving(false);
    }
  };

  const field =
    "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-100 outline-none transition focus:border-cyan-600";

  return (
    <div className="flex flex-col gap-4" data-testid="journal-panel">
      {/* Search */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h2 className="text-sm font-semibold text-zinc-100">Search journal</h2>
        <form
          className="mt-2 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void search(query);
          }}
        >
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by notes text…"
            aria-label="Search journal"
            data-testid="journal-search-input"
            className={field}
          />
          <button
            type="submit"
            data-testid="journal-search-button"
            className="shrink-0 rounded-lg bg-cyan-600 px-3.5 py-1.5 text-sm font-semibold text-white transition hover:bg-cyan-500"
          >
            Search
          </button>
        </form>
      </section>

      {/* Add entry */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h2 className="text-sm font-semibold text-zinc-100">Record journal entry</h2>
        <p className="text-xs text-zinc-500">Manual record — figures you enter are stored as-is.</p>
        <div className="mt-2 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <label className="text-xs text-zinc-400">
            Symbol
            <input value={symbol} onChange={(e) => setSymbol(e.target.value)} className={`${field} mt-1`} />
          </label>
          <label className="text-xs text-zinc-400">
            Timeframe
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className={`${field} mt-1`}>
              {["M1", "M5", "M15", "H1"].map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-zinc-400">
            Decision
            <select value={decision} onChange={(e) => setDecision(e.target.value)} className={`${field} mt-1`}>
              <option value="">—</option>
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
              <option value="WAIT">WAIT</option>
            </select>
          </label>
          <label className="text-xs text-zinc-400">
            Outcome
            <select value={outcome} onChange={(e) => setOutcome(e.target.value)} className={`${field} mt-1`}>
              {["PENDING", "WIN", "LOSS", "BE"].map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-zinc-400 col-span-2 sm:col-span-4">
            Notes
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Setup context, execution notes…"
              data-testid="journal-notes"
              className={`${field} mt-1 resize-y`}
            />
          </label>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            onClick={() => void save()}
            disabled={saving || notes.trim() === ""}
            data-testid="journal-save"
            className="rounded-lg bg-cyan-600 px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? "Saving…" : "Save entry"}
          </button>
          {saveOk && <span className="text-xs text-emerald-400">Entry saved.</span>}
        </div>
        {saveError != null && (
          <div className="mt-2">
            <ErrorState error={saveError} label="Could not save entry" />
          </div>
        )}
      </section>

      {/* Results */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h2 className="mb-2 text-sm font-semibold text-zinc-100">History</h2>
        {loading ? (
          <LoadingState label="Loading journal…" />
        ) : error ? (
          <ErrorState error={error} label="Journal search failed" onRetry={() => void search(query)} />
        ) : entries.length === 0 ? (
          <EmptyState
            title="No journal entries found"
            hint={query ? "Nothing matches this filter." : "Record your first entry above."}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" data-testid="journal-table">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  <th className="px-2 py-1.5 font-medium">Created (UTC)</th>
                  <th className="px-2 py-1.5 font-medium">Symbol</th>
                  <th className="px-2 py-1.5 font-medium">TF</th>
                  <th className="px-2 py-1.5 font-medium">Decision</th>
                  <th className="px-2 py-1.5 font-medium">Outcome</th>
                  <th className="px-2 py-1.5 font-medium">R:R</th>
                  <th className="px-2 py-1.5 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id} className="border-b border-zinc-800/60 text-zinc-300" data-testid="journal-row">
                    <td className="whitespace-nowrap px-2 py-1.5 font-mono">{formatUtc(e.created_at)}</td>
                    <td className="px-2 py-1.5 font-semibold">{e.symbol ?? "—"}</td>
                    <td className="px-2 py-1.5">{e.timeframe ?? "—"}</td>
                    <td className="px-2 py-1.5">{e.scenario_decision ?? "—"}</td>
                    <td className="px-2 py-1.5">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                          e.outcome === "WIN"
                            ? "bg-emerald-500/15 text-emerald-300"
                            : e.outcome === "LOSS"
                              ? "bg-red-500/15 text-red-300"
                              : "bg-zinc-700/60 text-zinc-300"
                        }`}
                      >
                        {e.outcome}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 font-mono">{e.rr !== null ? e.rr.toFixed(2) : "—"}</td>
                    <td className="max-w-[24ch] truncate px-2 py-1.5" title={e.notes}>
                      {e.notes || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

/** Exposed for error-shape assertions in tests. */
export type { ApiError };
