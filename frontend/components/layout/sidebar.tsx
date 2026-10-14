"use client";

/**
 * App sidebar (Phase 11D §3): collapsible on desktop (icon rail), drawer on
 * mobile. Collapse state persists per user preference.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const COLLAPSE_KEY = "nazbeen_sidebar_collapsed";

const NAV_ITEMS = [
  {
    href: "/dashboard",
    label: "Overview",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    href: "/dashboard/chart",
    label: "Chart",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
        <path d="M7 4v16M7 8h0M7 16h0" />
        <path d="M4 8h6v8H4z" />
        <path d="M17 4v16M14 7h6v7h-6z" />
      </svg>
    ),
  },
  {
    href: "/dashboard/analysis",
    label: "Analysis",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
        <path d="M12 16V4m0 0L7 9m5-5 5 5" />
        <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
      </svg>
    ),
  },
  {
    href: "/dashboard/history",
    label: "History",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 3" />
      </svg>
    ),
  },
  {
    href: "/dashboard/journal",
    label: "Journal",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
        <path d="M5 4a2 2 0 0 1 2-2h12v20H7a2 2 0 0 1-2-2z" />
        <path d="M9 7h6M9 11h6" />
      </svg>
    ),
  },
  {
    href: "/dashboard/backtests",
    label: "Backtests",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
        <path d="M4 19V5" />
        <path d="M4 19h16" />
        <path d="M8 15l3-4 3 2 4-6" />
      </svg>
    ),
  },
  {
    href: "/dashboard/analytics",
    label: "Analytics",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
        <path d="M5 20V10M12 20V4M19 20v-7" />
      </svg>
    ),
  },
  {
    href: "/dashboard/mentor",
    label: "AI Mentor",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
        <path d="M12 3a7 7 0 0 0-4 12.7V19h8v-3.3A7 7 0 0 0 12 3z" />
        <path d="M9 22h6" />
      </svg>
    ),
  },
  {
    href: "/dashboard/settings",
    label: "Settings",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5" aria-hidden>
        <circle cx="12" cy="12" r="3" />
        <path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z" />
      </svg>
    ),
  },
];

export function Sidebar({
  mobileOpen,
  onNavigate,
  onToggleCollapse,
}: {
  mobileOpen: boolean;
  onNavigate: () => void;
  onToggleCollapse: () => void;
}) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      /* preference persistence is best-effort */
    }
  }, []);

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* best-effort */
      }
      return next;
    });
    onToggleCollapse();
  };

  return (
    <>
      {/* Mobile drawer backdrop */}
      <div
        className={`fixed inset-0 z-30 bg-black/60 transition-opacity lg:hidden ${
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onNavigate}
        aria-hidden
        data-testid="sidebar-backdrop"
      />

      <aside
        data-testid="sidebar"
        aria-label="Primary navigation"
        className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-zinc-800 bg-[#0c1118] transition-all lg:static lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } ${collapsed ? "w-16" : "w-60"}`}
      >
        <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-zinc-800 px-4">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-700 font-mono text-sm font-bold">
            N
          </span>
          {!collapsed && (
            <span className="truncate text-sm font-semibold tracking-tight">
              Nazbeen<span className="text-zinc-400">Forex</span>
            </span>
          )}
        </div>

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                title={collapsed ? item.label : undefined}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  active
                    ? "bg-cyan-500/10 text-cyan-300"
                    : "text-zinc-400 hover:bg-zinc-800/70 hover:text-zinc-100"
                }`}
              >
                {item.icon}
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-zinc-800 p-2">
          <button
            type="button"
            onClick={toggle}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            data-testid="sidebar-collapse"
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-xs text-zinc-500 transition hover:bg-zinc-800/70 hover:text-zinc-300"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className={`h-4 w-4 transition-transform ${collapsed ? "rotate-180" : ""}`}
              aria-hidden
            >
              <path d="M15 6l-6 6 6 6" />
            </svg>
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>
    </>
  );
}
