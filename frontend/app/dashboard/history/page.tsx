"use client";

/** Analysis history (Phase 11D §8): owner-scoped list with reopen links. */

import { HistoryList } from "@/components/history/history-list";

export default function HistoryPage() {
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-base font-semibold text-zinc-100">Analysis history</h1>
        <p className="text-xs text-zinc-500">
          Your saved screenshot analyses (newest first) — reopen any entry to inspect its
          evidence, disagreements and uncertainty in full.
        </p>
      </header>
      <HistoryList />
    </div>
  );
}
