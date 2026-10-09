import { StatusCards } from "@/components/status-cards";
import { AuthPanel } from "@/components/auth-panel";

/**
 * Initial dashboard shell (Phase 1).
 *
 * Dark, minimal trading-desk UI. No trading logic, no AI analysis, no market data —
 * those arrive in Phases 9+ (analysis workspace, charts, journal, mentor chat).
 * All data flows through the same-origin /api proxy to the Django backend.
 */
export default function Page() {
  return (
    <div className="flex h-screen flex-col bg-[#0a0e14] text-zinc-100">
      <aside className="flex shrink-0 flex-col border-r border-zinc-800 px-4 py-5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-700 font-mono text-sm font-bold">
            N
          </span>
          <span className="text-lg font-semibold tracking-tight">
            Nazbeen<span className="text-zinc-400">Forex</span> AI
          </span>
        </div>
        <nav className="mt-6 flex flex-col gap-1.5 text-sm font-medium">
          <a
            className="flex items-center gap-2 rounded-lg bg-zinc-800 px-3 py-2 transition hover:bg-zinc-700"
            aria-current="page"
          >
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Overview
          </a>
          {[
            { label: "Analysis", note: "Phase 6+", active: false },
            { label: "Journal", note: "Phase 8+", active: false },
            { label: "Settings", note: "Phase 2+", active: false },
          ].map((item) => (
            <a
              key={item.label}
              className={`flex items-center justify-between rounded-lg px-3 py-2 transition ${
                item.active
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:bg-zinc-800/70 hover:text-zinc-100"
              }`}
            >
              <span>{item.label}</span>
              <span className="text-xs">{item.note}</span>
            </a>
          ))}
        </nav>
      </aside>

      <main className="flex flex-1 flex-col overflow-y-auto">
        <header className="flex shrink-0 items-center justify-between border-b border-zinc-800 px-4 py-3">
          <div>
            <h1 className="text-lg font-semibold">Overview</h1>
            <p className="text-xs text-zinc-500">
              Analysis-only decision support — no live trading. UTC displayed.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-xs text-zinc-500">
              <span className="font-medium text-zinc-300">UTC</span>
              <time dateTime="2026-10-08T04:30:00Z">04:30</time>
            </div>
            <div className="text-xs text-zinc-500">
              <span className="font-medium text-zinc-300">Market:</span>
              <span className="text-zinc-100">EURUSD · M15 primary</span>
            </div>
            <div className="pt-1"><AuthPanel /></div>
          </div>
        </header>

        <div className="px-4 py-4">
          <StatusCards />
        </div>
      </main>
    </div>
  );
}
