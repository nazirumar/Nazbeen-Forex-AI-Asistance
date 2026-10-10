import type { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: "Dashboard — Nazbeen Forex AI Asistance",
};

/** Protected dashboard wrapper (client-side session guard lives in AppShell). */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
