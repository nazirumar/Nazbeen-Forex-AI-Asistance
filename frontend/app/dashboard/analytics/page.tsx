"use client";

/** Journal analytics + export (Phase 11G §P2.5): recorded data only. */

import { AnalyticsPanel } from "@/components/analytics/analytics-panel";

export default function AnalyticsPage() {
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-base font-semibold text-zinc-100">Analytics</h1>
        <p className="text-xs text-zinc-500">
          Performance computed only from the fields you recorded. A statistic with no supporting
          data is shown as “—”, never as a fabricated zero.
        </p>
      </header>
      <AnalyticsPanel />
    </div>
  );
}
