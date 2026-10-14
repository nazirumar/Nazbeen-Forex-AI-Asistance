"use client";

/**
 * Account settings (Phase 11G §P2.5).
 *
 * Reads `GET /api/auth/me/`. This is **read-only on purpose**: the backend has
 * no profile-update endpoint yet, so no fake "save" control is shown — the page
 * states plainly that editing is not available. Nothing here is invented.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatUtc } from "@/lib/format";
import type { Me } from "@/lib/types";
import { ErrorState, LoadingState } from "@/components/ui/states";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-zinc-800/60 py-2 last:border-b-0">
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="truncate font-mono text-xs text-zinc-200">{value}</dd>
    </div>
  );
}

export function SettingsPanel() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await api<Me>("/api/auth/me/");
        if (active) setMe(res);
      } catch (err) {
        if (active) setError(err);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (loading) return <LoadingState label="Loading account…" />;
  if (error) return <ErrorState error={error} label="Account unavailable" />;
  if (!me) return null;

  return (
    <div className="flex flex-col gap-4" data-testid="settings-panel">
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h2 className="text-sm font-semibold text-zinc-100">Account</h2>
        <dl className="mt-2">
          <Row label="Username" value={me.username} />
          <Row label="Email" value={me.email || "—"} />
          <Row label="Joined (UTC)" value={formatUtc(me.date_joined)} />
          <Row label="Display timezone" value={me.profile?.display_timezone || "UTC"} />
        </dl>
        <p className="mt-3 text-[11px] text-zinc-500" data-testid="settings-readonly-note">
          Profile editing is not available yet — this backend exposes no
          account-update endpoint, so no values can be changed from here.
        </p>
      </section>
    </div>
  );
}
