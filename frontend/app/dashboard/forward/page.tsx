"use client";

/**
 * Forward testing (Phase 11G §9): start a *simulated* forward test, step it
 * forward, and inspect recorded decisions and outcomes. No orders are placed —
 * every figure is a recorded simulated observation, and `null` renders as "—".
 */

import { ForwardTestConsole } from "@/components/forwardtests/forwardtest-console";

export default function ForwardTestingPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-base font-semibold text-zinc-100">Forward testing</h1>
        <p className="text-xs text-zinc-500">
          Simulated forward testing. The deterministic engine is observed on fetched candles; the
          platform places no orders and results are not live trading performance.
        </p>
      </header>
      <ForwardTestConsole />
    </div>
  );
}
