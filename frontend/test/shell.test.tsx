/**
 * Dashboard shell & responsive layout tests (Phase 11D §2/§3).
 *
 * Covers: session guard redirect, protected content gating, mobile drawer
 * behaviour and desktop collapse — the mobile-responsibility checks for this
 * phase are structural (classes/ARIA), since no visual-regression tooling is
 * configured.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/app-shell";
import { Sidebar } from "@/components/layout/sidebar";
import { getToken, setToken } from "@/lib/api";
import { AuthProvider } from "@/lib/auth";
import { candlesFixture, fetchQueue, jsonResponse, statusFixture, stubFetch } from "./helpers";

const nav = vi.hoisted(() => ({
  replace: vi.fn(),
  pathname: "/dashboard",
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => nav.pathname,
}));

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  nav.replace.mockClear();
  nav.pathname = "/dashboard";
});

const ME = {
  id: 1,
  username: "trader1",
  email: "",
  date_joined: "2026-10-01T10:00:00Z",
  profile: { display_timezone: "UTC" },
};

function renderShell() {
  return render(
    <AuthProvider>
      <AppShell>
        <p data-testid="protected-content">secret</p>
      </AppShell>
    </AuthProvider>,
  );
}

describe("AppShell (protected routes)", () => {
  it("shows a session-check state and redirects anonymous users to login", async () => {
    stubFetch();
    renderShell();
    // Guard resolves to anonymous → redirect with the expiry reason.
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login?reason=expired"));
    expect(screen.queryByTestId("protected-content")).toBeNull();
  });

  it("redirects to plain login when no session ever existed", async () => {
    // No token and no reason: still anonymous, still redirected to login.
    stubFetch();
    renderShell();
    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
    expect(screen.queryByTestId("protected-content")).toBeNull();
  });

  it("renders the full shell once the session is validated", async () => {
    setToken("valid");
    fetchQueue([jsonResponse(ME), jsonResponse(statusFixture()), jsonResponse(candlesFixture())]);
    renderShell();

    await waitFor(() => expect(screen.getByTestId("protected-content")).toBeInTheDocument());
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("symbol-select")).toBeInTheDocument();
    expect(screen.getByTestId("timeframe-select")).toBeInTheDocument();
    expect(screen.getByTestId("connection-indicator")).toBeInTheDocument();
    expect(screen.getByTestId("freshness-indicator")).toBeInTheDocument();
    expect(getToken()).toBe("valid");
  });

  it("shows honest indicators when the status endpoint is unreachable", async () => {
    setToken("valid");
    fetchQueue([
      jsonResponse(ME),
      jsonResponse({ detail: "boom" }, 500), // status fails
      jsonResponse(candlesFixture()),
    ]);
    renderShell();
    await waitFor(() => expect(screen.getByTestId("protected-content")).toBeInTheDocument());
    await waitFor(() =>
      expect(screen.getByTestId("connection-indicator").textContent).toContain("unknown"),
    );
  });

  it("profile menu exposes logout", async () => {
    setToken("valid");
    fetchQueue([
      jsonResponse(ME),
      jsonResponse(statusFixture()),
      jsonResponse(candlesFixture()),
      jsonResponse({ detail: "Logged out." }),
    ]);
    renderShell();
    await waitFor(() => expect(screen.getByTestId("profile-menu-toggle")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("profile-menu-toggle"));
    expect(screen.getByTestId("profile-menu")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("logout-button"));
    await waitFor(() => expect(getToken()).toBeNull());
  });
});

describe("Sidebar (mobile drawer + desktop collapse)", () => {
  const props = { onNavigate: vi.fn(), onToggleCollapse: vi.fn() };

  it("is off-canvas when the mobile drawer is closed and slides in when open", () => {
    const { rerender } = render(<Sidebar {...props} mobileOpen={false} />);
    const aside = screen.getByTestId("sidebar");
    expect(aside.className).toContain("-translate-x-full");
    rerender(<Sidebar {...props} mobileOpen={true} />);
    expect(screen.getByTestId("sidebar").className).toContain("translate-x-0");
  });

  it("backdrop click closes the drawer (via onNavigate)", () => {
    render(<Sidebar {...props} mobileOpen={true} />);
    fireEvent.click(screen.getByTestId("sidebar-backdrop"));
    expect(props.onNavigate).toHaveBeenCalled();
  });

  it("collapse toggles the icon-rail width and hides labels", () => {
    render(<Sidebar {...props} mobileOpen={false} />);
    const aside = screen.getByTestId("sidebar");
    expect(aside.className).toContain("w-60");
    fireEvent.click(screen.getByTestId("sidebar-collapse"));
    expect(screen.getByTestId("sidebar").className).toContain("w-16");
    expect(screen.queryByText("Collapse")).toBeNull();
  });

  it("renders every navigation target and marks the active route", () => {
    nav.pathname = "/dashboard/chart";
    render(<Sidebar {...props} mobileOpen={false} />);
    const links = screen.getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual([
      "/dashboard",
      "/dashboard/chart",
      "/dashboard/analysis",
      "/dashboard/history",
      "/dashboard/journal",
    ]);
    expect(screen.getByText("Chart").closest("a")?.getAttribute("aria-current")).toBe("page");
  });
});
