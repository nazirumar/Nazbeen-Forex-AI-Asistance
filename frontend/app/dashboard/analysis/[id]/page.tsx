"use client";

/**
 * Reopen a saved analysis (Phase 11D §5/§8).
 *
 * Fetches `GET /api/analysis/{id}/` (owner-scoped server-side) and the stored
 * screenshot via the ownership-scoped image endpoint; a 404 there is reported
 * honestly as "not stored / not accessible" instead of a broken image.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, apiBlob, ApiError } from "@/lib/api";
import { AnalysisResultView } from "@/components/analysis/analysis-result";
import { ErrorState, LoadingState } from "@/components/ui/states";
import type { AnalysisDetail } from "@/lib/types";

export default function ReopenAnalysisPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageState, setImageState] = useState<"loading" | "ready" | "missing" | "error">("loading");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<AnalysisDetail>(`/api/analysis/${id}/`);
      setDetail(res);
    } catch (err) {
      setError(err);
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Screenshot as an authenticated blob (object URL, revoked on unmount).
  useEffect(() => {
    let url: string | null = null;
    let active = true;
    void (async () => {
      setImageState("loading");
      try {
        const blob = await apiBlob(`/api/analysis/${id}/screenshot/`);
        if (!active) return;
        url = URL.createObjectURL(blob);
        setImageUrl(url);
        setImageState("ready");
      } catch (err) {
        if (!active) return;
        setImageUrl(null);
        setImageState(err instanceof ApiError && err.status === 404 ? "missing" : "error");
      }
    })();
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [id]);

  if (loading) return <LoadingState label="Loading saved analysis…" />;
  if (error) {
    return (
      <div className="flex flex-col gap-3">
        <ErrorState error={error} label="Analysis could not be loaded" onRetry={() => void load()} />
        <Link href="/dashboard/history" className="text-xs text-cyan-400 hover:underline">
          ← Back to history
        </Link>
      </div>
    );
  }
  if (!detail) return <ErrorState error="Analysis not found" label="Missing analysis" />;

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-base font-semibold text-zinc-100">Saved analysis</h1>
          <p className="font-mono text-xs text-zinc-500">{id}</p>
        </div>
        <Link
          href="/dashboard/history"
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800"
        >
          ← Back to history
        </Link>
      </header>

      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h2 className="text-sm font-semibold text-zinc-100">Original screenshot</h2>
        {imageState === "loading" && <p className="mt-2 text-xs text-zinc-500">Loading screenshot…</p>}
        {imageState === "ready" && imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt="Uploaded chart screenshot"
            className="mt-2 max-h-80 w-full rounded-lg border border-zinc-800 object-contain bg-black"
            data-testid="reopen-screenshot"
          />
        )}
        {imageState === "missing" && (
          <p className="mt-2 text-xs text-zinc-500" data-testid="screenshot-missing">
            No screenshot is stored for this analysis (persistence can fail — the record is kept
            and labeled honestly).
          </p>
        )}
        {imageState === "error" && (
          <p className="mt-2 text-xs text-red-400">Screenshot could not be loaded.</p>
        )}
      </section>

      <AnalysisResultView result={detail.analysis} />
    </div>
  );
}
