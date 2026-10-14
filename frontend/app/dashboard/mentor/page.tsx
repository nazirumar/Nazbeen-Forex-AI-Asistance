"use client";

/** AI mentor chat (Phase 11G §P2.5): analysis-only explanations. */

import { MentorChat } from "@/components/mentor/mentor-chat";

export default function MentorPage() {
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-base font-semibold text-zinc-100">AI Mentor</h1>
        <p className="text-xs text-zinc-500">
          Ask about your saved analyses. Explanations are analysis-only — no trade execution and no
          guaranteed outcomes.
        </p>
      </header>
      <MentorChat />
    </div>
  );
}
