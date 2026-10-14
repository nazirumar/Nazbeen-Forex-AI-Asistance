"use client";

/** Account settings (Phase 11G §P2.5): read-only account view. */

import { SettingsPanel } from "@/components/settings/settings-panel";

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-base font-semibold text-zinc-100">Settings</h1>
        <p className="text-xs text-zinc-500">Your account details, as returned by the backend.</p>
      </header>
      <SettingsPanel />
    </div>
  );
}
