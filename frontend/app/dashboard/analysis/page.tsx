"use client";

/** Screenshot analysis workspace (Phase 11D §5). */

import { UploadPanel } from "@/components/analysis/upload-panel";

export default function AnalysisPage() {
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-base font-semibold text-zinc-100">Screenshot analysis</h1>
        <p className="text-xs text-zinc-500">
          Upload a PNG/JPEG chart screenshot — AI vision observations combined with deterministic
          ICT/SMC findings. Analysis-only; no orders are ever placed.
        </p>
      </header>
      <UploadPanel />
    </div>
  );
}
