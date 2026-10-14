"use client";

/**
 * Primary trading-model checklist (Phase 11E WP6).
 *
 * Renders the backend's seven-step chronological setup verbatim: each step's
 * real status (`satisfied` / `missing` / `invalid` / `unavailable`), confirming
 * timestamp and detail, plus the model name, completeness and `blocked_by`
 * reasons. When there is no checklist or the setup is incomplete it says so
 * explicitly — it never claims a setup exists, and it contains **no execution
 * controls** (analysis-only).
 */

import { deriveSetupChecklist } from "@/lib/chart-data";
import type { SetupResult } from "@/lib/types";

const STATUS_STYLE: Record<string, { label: string; cls: string; dot: string }> = {
  satisfied: { label: "Satisfied", cls: "text-emerald-300", dot: "bg-emerald-400" },
  missing: { label: "Missing", cls: "text-amber-300", dot: "bg-amber-400" },
  invalid: { label: "Invalid", cls: "text-red-300", dot: "bg-red-400" },
  unavailable: { label: "Unavailable", cls: "text-zinc-400", dot: "bg-zinc-600" },
};

function statusStyle(status: string): { label: string; cls: string; dot: string } {
  return STATUS_STYLE[status] ?? { label: status || "Unknown", cls: "text-zinc-400", dot: "bg-zinc-600" };
}

export function SetupChecklist({ setup }: { setup: SetupResult | null }) {
  const steps = deriveSetupChecklist(setup);
  const complete = setup?.complete === true;

  return (
    <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4" data-testid="setup-checklist">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">Primary setup checklist</h2>
          <p className="text-xs text-zinc-500" data-testid="setup-model">
            {setup ? setup.model : "No setup model output"}
            {setup?.as_of ? ` · as of ${setup.as_of}` : ""}
          </p>
        </div>
        <span
          data-testid="setup-state"
          className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
            complete ? "bg-emerald-500/15 text-emerald-300" : "bg-zinc-700/40 text-zinc-300"
          }`}
        >
          {complete ? `Complete · ${setup?.decision ?? "WAIT"}` : "Incomplete · WAIT"}
        </span>
      </header>

      {steps.length === 0 ? (
        <div
          data-testid="setup-empty"
          className="rounded-xl border border-dashed border-zinc-700 bg-zinc-900/30 px-4 py-6 text-center"
        >
          <p className="text-sm font-medium text-zinc-300">No setup yet</p>
          <p className="mt-1 text-xs text-zinc-500">
            Insufficient data — the engine has not produced a checklist. Nothing is shown instead of a
            fabricated setup.
          </p>
        </div>
      ) : (
        <>
          {!complete && (
            <p
              data-testid="setup-incomplete"
              className="mb-3 rounded-lg border border-amber-700/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-300"
            >
              No complete setup yet — insufficient confirmation, so the decision is WAIT. Analysis
              only, not a trade instruction.
            </p>
          )}
          <ol className="flex flex-col gap-1.5" data-testid="setup-steps">
            {steps.map((step, i) => {
              const style = statusStyle(step.status);
              return (
                <li
                  key={step.key}
                  data-testid={`setup-step-${step.key}`}
                  data-status={step.status}
                  className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 text-sm font-medium text-zinc-200">
                      <span className="font-mono text-xs text-zinc-500">{i + 1}</span>
                      {step.label}
                    </span>
                    <span className={`flex items-center gap-1.5 text-xs font-semibold ${style.cls}`}>
                      <span className={`h-2 w-2 rounded-full ${style.dot}`} aria-hidden />
                      {style.label}
                    </span>
                  </div>
                  {step.detail && <p className="mt-1 text-xs text-zinc-500">{step.detail}</p>}
                  {step.time && <p className="mt-0.5 font-mono text-[10px] text-zinc-600">{step.time}</p>}
                </li>
              );
            })}
          </ol>
        </>
      )}

      {setup && setup.blocked_by.length > 0 && (
        <div className="mt-3" data-testid="setup-blocked-by">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Blocked by</h3>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {setup.blocked_by.map((reason) => (
              <li
                key={reason}
                className="rounded-md border border-zinc-700 bg-zinc-800/60 px-2 py-1 text-xs text-zinc-300"
              >
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {complete && setup && setup.blocked_by.length === 0 && (
        <p className="mt-3 text-xs text-zinc-500">
          All seven confirmations are satisfied in chronological order. Analysis only — no trade
          execution.
        </p>
      )}
    </section>
  );
}
