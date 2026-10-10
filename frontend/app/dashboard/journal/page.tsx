"use client";

/** Trading journal (Phase 11D §8): search + manual entries, real fields only. */

import { JournalPanel } from "@/components/journal/journal-panel";

export default function JournalPage() {
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-base font-semibold text-zinc-100">Journal</h1>
        <p className="text-xs text-zinc-500">
          Record and search your trade ideas. Entries store exactly what you enter — no
          fabricated performance statistics.
        </p>
      </header>
      <JournalPanel />
    </div>
  );
}
