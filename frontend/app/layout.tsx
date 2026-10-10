import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Nazbeen Forex AI Asistance",
  description:
    "AI-powered Forex market analysis and decision-support platform (analysis-only).",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning: browser extensions (e.g. WebCRX bridging) inject
    // attributes onto <html> before React hydrates, which otherwise produces a
    // spurious mismatch warning. It applies to this element only — mismatches
    // anywhere deeper in the tree are still reported normally.
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased min-h-screen">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
