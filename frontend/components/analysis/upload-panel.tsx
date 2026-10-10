"use client";

/**
 * Screenshot analysis workspace (Phase 11D §5).
 *
 * PNG/JPEG upload with preview → POST /api/analysis/upload/ → processing
 * status → result view. Client-side checks mirror the backend validator
 * (5 MB, PNG/JPEG only) purely to fail fast — the backend remains the
 * authority and its 400 response is always displayed verbatim on rejection.
 */

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { AnalysisResult, Timeframe, UploadResponse } from "@/lib/types";
import { AnalysisResultView } from "./analysis-result";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { useMarket } from "@/components/layout/market-context";

const MAX_BYTES = 5 * 1024 * 1024; // mirrors analysis.validators.MAX_IMAGE_SIZE_BYTES
const ACCEPTED = ["image/png", "image/jpeg"];

type Phase = "idle" | "uploading" | "done";

export function UploadPanel() {
  const { symbol, timeframe } = useMarket();
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [screenshotStored, setScreenshotStored] = useState<boolean | null>(null);
  const [localRejection, setLocalRejection] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Object URL lifecycle — always revoked to avoid leaks.
  useEffect(() => {
    if (!file || typeof URL.createObjectURL !== "function") return;
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  const onPick = (picked: File | null) => {
    setLocalRejection(null);
    setError(null);
    if (!picked) return;
    if (!ACCEPTED.includes(picked.type)) {
      setFile(null);
      setLocalRejection("Only PNG or JPEG screenshots are supported.");
      return;
    }
    if (picked.size > MAX_BYTES) {
      setFile(null);
      setLocalRejection("Image too large. Max 5MB allowed.");
      return;
    }
    setFile(picked);
    setResult(null);
    setAnalysisId(null);
    setScreenshotStored(null);
  };

  const submit = async () => {
    if (!file) return;
    setPhase("uploading");
    setError(null);
    try {
      const form = new FormData();
      form.append("image", file);
      form.append("symbol", symbol);
      form.append("timeframe", timeframe);
      const res = await api<UploadResponse>("/api/analysis/upload/", { method: "POST", formData: form });
      setResult(res.result);
      setAnalysisId(res.analysis_id ?? null);
      setScreenshotStored(res.screenshot_stored);
      setPhase("done");
    } catch (err) {
      setError(err);
      setPhase("idle");
    }
  };

  return (
    <div className="flex flex-col gap-4" data-testid="upload-panel">
      {/* Upload card */}
      <section className="rounded-2xl border border-zinc-800 bg-[#0c1118] p-4">
        <h2 className="text-sm font-semibold text-zinc-100">Upload screenshot</h2>
        <p className="mt-0.5 text-xs text-zinc-500">
          PNG or JPEG, max 5 MB. Submitted for {symbol} · {timeframe} (your current selection).
        </p>

        <label
          className="mt-3 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-zinc-700 bg-zinc-900/40 px-4 py-6 text-center transition hover:border-cyan-700"
          data-testid="upload-dropzone"
        >
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg"
            className="sr-only"
            data-testid="file-input"
            onChange={(e) => onPick(e.target.files?.[0] ?? null)}
          />
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-6 w-6 text-zinc-500" aria-hidden>
            <path d="M12 16V4m0 0L7 9m5-5 5 5" />
            <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
          </svg>
          <span className="text-xs text-zinc-400">
            {file ? file.name : "Click to choose a chart screenshot"}
          </span>
        </label>

        {localRejection && (
          <p role="alert" className="mt-2 text-xs text-red-400" data-testid="upload-rejection">
            {localRejection}
          </p>
        )}

        {previewUrl && (
          <div className="mt-3 overflow-hidden rounded-xl border border-zinc-800" data-testid="upload-preview">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previewUrl} alt="Screenshot preview" className="max-h-72 w-full object-contain bg-black" />
          </div>
        )}

        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            onClick={() => void submit()}
            disabled={!file || phase === "uploading"}
            data-testid="submit-analysis"
            className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {phase === "uploading" ? "Analyzing…" : "Run analysis"}
          </button>
          {file && phase !== "uploading" && (
            <button
              type="button"
              onClick={() => {
                setFile(null);
                if (inputRef.current) inputRef.current.value = "";
              }}
              className="text-xs text-zinc-500 underline-offset-2 hover:text-zinc-300 hover:underline"
            >
              Clear
            </button>
          )}
          {phase === "uploading" && (
            <span className="text-xs text-zinc-500">Analysis runs on the backend — this may take a moment.</span>
          )}
        </div>
      </section>

      {phase === "uploading" && <LoadingState label="Processing screenshot analysis…" />}

      {error != null && (
        <ErrorState
          error={error}
          label={
            error instanceof ApiError && error.status === 400
              ? "Upload rejected by the backend"
              : "Analysis request failed"
          }
        />
      )}

      {phase === "done" && result && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <span>
              Saved as analysis{" "}
              <span className="font-mono text-zinc-300">{analysisId ?? "not persisted"}</span>
            </span>
            <span>·</span>
            <span>{screenshotStored ? "Screenshot stored" : "Screenshot not stored"}</span>
            {analysisId && (
              <a href="/dashboard/history" className="text-cyan-400 underline-offset-2 hover:underline">
                Reopen from History →
              </a>
            )}
          </div>
          <AnalysisResultView result={result} />
        </div>
      )}
    </div>
  );
}
