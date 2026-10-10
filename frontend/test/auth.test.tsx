/**
 * Auth session tests (Phase 11D §2): token persistence, session re-validation
 * on boot, login/register/logout, and expiry handling.
 */

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AUTH_EXPIRED_EVENT, getToken, setToken } from "@/lib/api";
import { AuthProvider, useAuth } from "@/lib/auth";
import { fetchQueue, jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

const ME = {
  id: 1,
  username: "trader1",
  email: "t@example.com",
  date_joined: "2026-10-01T10:00:00Z",
  profile: { display_timezone: "UTC" },
};

/** Last promise created by the probe's buttons (for rejection assertions). */
let pending: Promise<void> | null = null;

function Probe() {
  const { status, user, login, logout, register } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{user?.username ?? "none"}</span>
      <button data-testid="do-login" onClick={() => (pending = login("trader1", "pw"))}>
        login
      </button>
      <button data-testid="do-register" onClick={() => (pending = register("trader1", "", "Str0ng-Pass!"))}>
        register
      </button>
      <button data-testid="do-logout" onClick={() => (pending = logout())}>
        logout
      </button>
    </div>
  );
}

function renderAuth() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

describe("AuthProvider", () => {
  it("starts anonymous without a stored token", async () => {
    stubFetch();
    renderAuth();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));
  });

  it("re-validates a stored token against /api/auth/me/ on boot", async () => {
    setToken("valid-token");
    fetchQueue([jsonResponse(ME)]);
    renderAuth();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    expect(screen.getByTestId("user").textContent).toBe("trader1");
  });

  it("clears a revoked token on boot and lands anonymous", async () => {
    setToken("revoked");
    fetchQueue([jsonResponse({ detail: "Invalid token." }, 401)]);
    renderAuth();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));
    expect(getToken()).toBeNull();
  });

  it("login persists the token and loads the profile", async () => {
    const fn = fetchQueue([
      jsonResponse({ token: "fresh-token", user: { id: 1, username: "trader1" } }),
      jsonResponse(ME),
    ]);
    renderAuth();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));

    await act(async () => {
      fireEvent.click(screen.getByTestId("do-login"));
      await pending;
    });
    expect(getToken()).toBe("fresh-token");
    expect(screen.getByTestId("status").textContent).toBe("authenticated");
    // login POST first, then the /me validation GET with the new token
    expect(String(fn.mock.calls[0][0])).toContain("/api/auth/login/");
    expect(String(fn.mock.calls[1][0])).toContain("/api/auth/me/");
  });

  it("register persists the token too", async () => {
    fetchQueue([
      jsonResponse({ token: "reg-token", user: { id: 2, username: "trader1" } }, 201),
      jsonResponse({ ...ME, id: 2 }),
    ]);
    renderAuth();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));

    await act(async () => {
      fireEvent.click(screen.getByTestId("do-register"));
      await pending;
    });
    expect(getToken()).toBe("reg-token");
    expect(screen.getByTestId("status").textContent).toBe("authenticated");
  });

  it("surfaces backend login errors and stays anonymous", async () => {
    fetchQueue([jsonResponse({ detail: "Invalid credentials." }, 400)]);
    renderAuth();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));

    let caught: unknown = null;
    await act(async () => {
      fireEvent.click(screen.getByTestId("do-login"));
      await pending!.catch((e) => {
        caught = e;
      });
    });
    expect(caught).toMatchObject({ status: 400 });
    expect(getToken()).toBeNull();
    expect(screen.getByTestId("status").textContent).toBe("anonymous");
  });

  it("logout clears the local session even when the server revoke fails", async () => {
    setToken("tok");
    fetchQueue([
      jsonResponse(ME), // boot /me
      new Response("", { status: 500 }), // logout fails server-side
    ]);
    renderAuth();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));

    await act(async () => {
      fireEvent.click(screen.getByTestId("do-logout"));
      await pending;
    });
    expect(getToken()).toBeNull();
    expect(screen.getByTestId("status").textContent).toBe("anonymous");
  });

  it("an auth-expired event (401 anywhere) ends the session with a reason", async () => {
    setToken("expired");
    fetchQueue([jsonResponse(ME)]);
    renderAuth();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));

    act(() => {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    });
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));
    expect(getToken()).toBeNull();
    expect(window.sessionStorage.getItem("nazbeen_auth_reason")).toBe("expired");
  });
});
