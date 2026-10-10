"use client";

/**
 * Protected dashboard shell (Phase 11D §2/§3).
 *
 * - While the stored token is being validated, a neutral "checking session"
 *   screen is shown — nothing protected renders before verification.
 * - Anonymous users are redirected to /login (with `reason=expired` when the
 *   session ended because the backend rejected it).
 * - Authenticated users get the responsive sidebar + topbar layout.
 */

import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { MarketProvider } from "./market-context";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

export function AppShell({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (status === "anonymous") {
      router.replace("/login?reason=expired");
    }
  }, [status, router, pathname]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (status === "loading") {
    return (
      <div
        className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[#0a0e14] text-zinc-400"
        data-testid="checking-session"
      >
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
        <p className="text-sm">Checking session…</p>
      </div>
    );
  }

  if (status === "anonymous") {
    // Redirecting — keep the screen blank instead of flashing protected UI.
    return <div className="min-h-screen bg-[#0a0e14]" />;
  }

  return (
    <MarketProvider>
      <div className="flex h-screen overflow-hidden bg-[#0a0e14] text-zinc-100">
        <Sidebar
          mobileOpen={mobileOpen}
          onNavigate={() => setMobileOpen(false)}
          onToggleCollapse={() => undefined}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onOpenSidebar={() => setMobileOpen(true)} />
          <main className="flex-1 overflow-y-auto p-3 sm:p-4 lg:p-5">{children}</main>
        </div>
      </div>
    </MarketProvider>
  );
}
