"use client";

/**
 * Landing route (Phase 11D): sends users to the dashboard when a session is
 * confirmed, otherwise to the login screen. Until the stored token has been
 * validated against the backend a neutral loading state is shown — protected
 * content never flashes before verification.
 */

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

export default function Page() {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[#0a0e14] text-zinc-400"
      data-testid="landing-loading"
    >
      <span className="h-6 w-6 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
      <p className="text-sm">Loading Nazbeen Forex AI…</p>
    </div>
  );
}
