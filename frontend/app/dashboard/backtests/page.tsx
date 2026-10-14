"use client";

/**
 * Backtests (Phase 11G §7): run/inspect a simulated backtest and browse the
 * recorded history. Every figure is a stored simulated result — `null` renders
 * as "—" and is never replaced with a guessed value.
 */

import { BacktestConsole } from "@/components/backtests/backtest-console";
import { BacktestList } from "@/components/backtests/backtest-list";

export default function BacktestsPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-base font-semibold text-zinc-100">Backtests</h1>
        <p className="text-xs text-zinc-500">
          Simulated historical evaluation. No orders are placed; a blank metric means the value was
          not computable from the recorded trades.
        </p>
      </header>
      <BacktestConsole />
      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-zinc-100">History</h2>
        <BacktestList />
      </section>
    </div>
  );
}
