"use client";

/**
 * Risk management panel (Phase 11D §7).
 *
 * Inputs are validated by the backend (`POST /api/risk/trade-plan/`) and only
 * the numbers the backend actually returns are displayed — missing values
 * render as "—", never as an assumed default. This panel is analysis-only:
 * there are intentionally **no trade execution controls** anywhere in it.
 */

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatPrice, formatRatio } from "@/lib/format";
import type { TradePlan } from "@/lib/types";
import { useMarket } from "@/components/layout/market-context";
import { ErrorState } from "@/components/ui/states";

export function RiskPanel({ onPlan }: { onPlan?: (plan: TradePlan | null) => void }) {
  const { symbol } = useMarket();
  const [bias, setBias] = useState<"bullish" | "bearish" | "neutral">("bullish");
  const [balance, setBalance] = useState("10000");
  const [riskPercent, setRiskPercent] = useState("1");
  const [entry, setEntry] = useState("");
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [spread, setSpread] = useState("");
  const [plan, setPlan] = useState<TradePlan | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  const num = (v: string): number | undefined => {
    if (v.trim() === "") return undefined;
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  };

  const compute = async () => {
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        symbol,
        bias,
        account_balance: Number(balance),
        risk_percent: Number(riskPercent),
      };
      const e = num(entry);
      const s = num(sl);
      const t = num(tp);
      const sp = num(spread);
      if (e !== undefined) body.entry = e;
      if (s !== undefined) body.sl = s;
      if (t !== undefined) body.tp = t;
      if (sp !== undefined) body.spread_pips = sp;
      const res = await api<TradePlan>("/api/risk/trade-plan/", { method: "POST", body });
      setPlan(res);
      onPlan?.(res);
    } catch (err) {
      setError(err);
      setPlan(null);
      onPlan?.(null);
    } finally {
      setLoading(false);
    }
  };

  const field =
    "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-100 outline-none transition focus:border-cyan-600";

  return (
    <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4" data-testid="risk-panel">
      <header className="mb-3">
        <h2 className="text-sm font-semibold text-zinc-100">Risk management</h2>
        <p className="text-xs text-zinc-500">
          Validated by the backend scenario engine · analysis only, no execution
        </p>
      </header>

      <div className="grid grid-cols-2 gap-2.5">
        <label className="text-xs text-zinc-400">
          Bias
          <select
            value={bias}
            onChange={(e) => setBias(e.target.value as typeof bias)}
            className={`${field} mt-1`}
            data-testid="risk-bias"
          >
            <option value="bullish">Bullish</option>
            <option value="bearish">Bearish</option>
            <option value="neutral">Neutral</option>
          </select>
        </label>
        <label className="text-xs text-zinc-400">
          Account balance
          <input
            type="number"
            min="0"
            step="100"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
            className={`${field} mt-1`}
            data-testid="risk-balance"
          />
        </label>
        <label className="text-xs text-zinc-400">
          Risk %
          <input
            type="number"
            min="0"
            max="10"
            step="0.1"
            value={riskPercent}
            onChange={(e) => setRiskPercent(e.target.value)}
            className={`${field} mt-1`}
            data-testid="risk-percent"
          />
        </label>
        <label className="text-xs text-zinc-400">
          Spread (pips)
          <input
            type="number"
            min="0"
            step="0.1"
            placeholder="optional"
            value={spread}
            onChange={(e) => setSpread(e.target.value)}
            className={`${field} mt-1`}
          />
        </label>
        <label className="text-xs text-zinc-400">
          Entry
          <input
            type="number"
            step="0.00001"
            placeholder="optional"
            value={entry}
            onChange={(e) => setEntry(e.target.value)}
            className={`${field} mt-1`}
            data-testid="risk-entry"
          />
        </label>
        <label className="text-xs text-zinc-400">
          Stop loss
          <input
            type="number"
            step="0.00001"
            placeholder="optional"
            value={sl}
            onChange={(e) => setSl(e.target.value)}
            className={`${field} mt-1`}
            data-testid="risk-sl"
          />
        </label>
        <label className="text-xs text-zinc-400 col-span-2">
          Take profit
          <input
            type="number"
            step="0.00001"
            placeholder="optional"
            value={tp}
            onChange={(e) => setTp(e.target.value)}
            className={`${field} mt-1`}
            data-testid="risk-tp"
          />
        </label>
      </div>

      <button
        type="button"
        onClick={() => void compute()}
        disabled={loading}
        data-testid="compute-plan"
        className="mt-3 w-full rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Evaluating…" : "Evaluate plan"}
      </button>

      {error != null && (
        <div className="mt-3">
          <ErrorState
            error={error}
            label={error instanceof ApiError && error.status === 400 ? "Invalid trade plan input" : "Risk evaluation failed"}
          />
        </div>
      )}

      {plan && (
        <div className="mt-3 flex flex-col gap-3" data-testid="risk-result">
          <div className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2">
            <span className="text-xs text-zinc-500">Decision</span>
            <span
              data-testid="plan-decision"
              className={`text-sm font-bold ${
                plan.decision === "BUY"
                  ? "text-emerald-300"
                  : plan.decision === "SELL"
                    ? "text-red-300"
                    : "text-zinc-300"
              }`}
            >
              {plan.decision}
            </span>
          </div>

          <dl className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg bg-zinc-900/60 p-2">
              <dt className="text-zinc-500">Entry</dt>
              <dd className="mt-0.5 font-mono text-zinc-100" data-testid="plan-entry">
                {plan.entry_levels.length ? formatPrice(plan.entry_levels[0]) : "—"}
              </dd>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-2">
              <dt className="text-zinc-500">Stop loss</dt>
              <dd className="mt-0.5 font-mono text-zinc-100" data-testid="plan-sl">
                {formatPrice(plan.sl)}
              </dd>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-2">
              <dt className="text-zinc-500">Take profit</dt>
              <dd className="mt-0.5 font-mono text-zinc-100" data-testid="plan-tp">
                {formatPrice(plan.tp)}
              </dd>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-2">
              <dt className="text-zinc-500">Risk / reward</dt>
              <dd className="mt-0.5 font-mono text-zinc-100" data-testid="plan-rr">
                {formatRatio(plan.rr)}
              </dd>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-2">
              <dt className="text-zinc-500">Account risk %</dt>
              <dd className="mt-0.5 font-mono text-zinc-100">{riskPercent}%</dd>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-2">
              <dt className="text-zinc-500">Position size (lots)</dt>
              <dd className="mt-0.5 font-mono text-zinc-100" data-testid="plan-lots">
                {formatRatio(plan.lot_size)}
              </dd>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-2">
              <dt className="text-zinc-500">Spread (pips)</dt>
              <dd className="mt-0.5 font-mono text-zinc-100">
                {spread.trim() === "" ? "—" : spread}
              </dd>
            </div>
            <div className="rounded-lg bg-zinc-900/60 p-2">
              <dt className="text-zinc-500">Confluence (not probability)</dt>
              <dd className="mt-0.5 font-mono text-zinc-100">
                {typeof plan.confluence_score === "number" ? plan.confluence_score.toFixed(2) : "—"}
              </dd>
            </div>
          </dl>

          {plan.reasons.length > 0 && (
            <ul className="flex flex-col gap-1" data-testid="plan-reasons">
              {plan.reasons.map((r) => (
                <li key={r} className="text-xs text-zinc-400">
                  · {r}
                </li>
              ))}
            </ul>
          )}

          {plan.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-700/50 bg-amber-500/10 p-2.5" data-testid="plan-warnings">
              <p className="text-xs font-semibold text-amber-300">Setup warnings</p>
              <ul className="mt-1 flex flex-col gap-1">
                {plan.warnings.map((w) => (
                  <li key={w} className="text-xs text-amber-200/90">
                    ⚠ {w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
