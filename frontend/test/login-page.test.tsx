/**
 * Login / registration screens (Phase 11D §2): credential errors are shown
 * verbatim, expired sessions are announced, and the repaired token flow
 * navigates to the dashboard only after a successful sign-in.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginPage from "@/app/login/page";
import RegisterPage from "@/app/register/page";
import { getToken } from "@/lib/api";
import { AuthProvider } from "@/lib/auth";
import { fetchQueue, jsonResponse, stubFetch } from "./helpers";

const nav = vi.hoisted(() => ({
  replace: vi.fn(),
  search: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace }),
  useSearchParams: () => nav.search,
}));

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  nav.replace.mockClear();
  nav.search = new URLSearchParams();
});

function renderLogin() {
  return render(
    <AuthProvider>
      <LoginPage />
    </AuthProvider>,
  );
}

describe("LoginPage", () => {
  it("shows the backend's credential error verbatim and stays signed out", async () => {
    fetchQueue([jsonResponse({ detail: "Invalid credentials." }, 400)]);
    renderLogin();

    fireEvent.change(screen.getByTestId("login-username"), { target: { value: "trader1" } });
    fireEvent.change(screen.getByTestId("login-password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByTestId("login-submit"));

    const err = await screen.findByTestId("login-error");
    expect(err.textContent).toContain("Invalid credentials.");
    expect(getToken()).toBeNull();
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("announces an expired session with the banner", async () => {
    stubFetch();
    nav.search = new URLSearchParams("reason=expired");
    renderLogin();
    expect(await screen.findByTestId("session-expired-banner")).toBeInTheDocument();
  });

  it("completes the repaired token flow and navigates to the dashboard", async () => {
    fetchQueue([
      jsonResponse({ token: "new-token", user: { id: 1, username: "trader1" } }),
      jsonResponse({
        id: 1,
        username: "trader1",
        email: "",
        date_joined: "2026-10-01T10:00:00Z",
        profile: { display_timezone: "UTC" },
      }),
    ]);
    renderLogin();

    fireEvent.change(screen.getByTestId("login-username"), { target: { value: "trader1" } });
    fireEvent.change(screen.getByTestId("login-password"), { target: { value: "pw" } });
    fireEvent.click(screen.getByTestId("login-submit"));

    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/dashboard"));
    expect(getToken()).toBe("new-token");
  });

  it("shows a server-unreachable hint when the backend is down", async () => {
    fetchQueue([new Error("ECONNREFUSED")]);
    renderLogin();

    fireEvent.change(screen.getByTestId("login-username"), { target: { value: "trader1" } });
    fireEvent.change(screen.getByTestId("login-password"), { target: { value: "pw" } });
    fireEvent.click(screen.getByTestId("login-submit"));

    const err = await screen.findByTestId("login-error");
    expect(err.textContent).toContain("backend running");
  });
});

describe("RegisterPage", () => {
  function renderRegister() {
    return render(
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>,
    );
  }

  it("blocks submission when passwords do not match", async () => {
    stubFetch();
    renderRegister();
    fireEvent.change(screen.getByTestId("register-username"), { target: { value: "u1" } });
    fireEvent.change(screen.getByTestId("register-password"), { target: { value: "Str0ng-Pass!" } });
    fireEvent.change(screen.getByTestId("register-confirm"), { target: { value: "different" } });
    fireEvent.click(screen.getByTestId("register-submit"));
    const err = await screen.findByTestId("register-error");
    expect(err.textContent).toContain("Passwords do not match");
  });

  it("renders Django password-validation messages field-by-field", async () => {
    fetchQueue([
      jsonResponse(
        { password: ["This password is too common."] },
        400,
      ),
    ]);
    renderRegister();
    fireEvent.change(screen.getByTestId("register-username"), { target: { value: "u1" } });
    fireEvent.change(screen.getByTestId("register-password"), { target: { value: "password" } });
    fireEvent.change(screen.getByTestId("register-confirm"), { target: { value: "password" } });
    fireEvent.click(screen.getByTestId("register-submit"));
    const fieldErr = await screen.findByTestId("register-password-error");
    expect(fieldErr.textContent).toContain("This password is too common.");
    expect(getToken()).toBeNull();
  });

  it("signs the user in after successful registration", async () => {
    fetchQueue([
      jsonResponse({ token: "reg-token", user: { id: 2, username: "u1" } }, 201),
      jsonResponse({
        id: 2,
        username: "u1",
        email: "",
        date_joined: "2026-10-01T10:00:00Z",
        profile: { display_timezone: "UTC" },
      }),
    ]);
    renderRegister();
    fireEvent.change(screen.getByTestId("register-username"), { target: { value: "u1" } });
    fireEvent.change(screen.getByTestId("register-password"), { target: { value: "Str0ng-Pass!" } });
    fireEvent.change(screen.getByTestId("register-confirm"), { target: { value: "Str0ng-Pass!" } });
    fireEvent.click(screen.getByTestId("register-submit"));
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/dashboard"));
    expect(getToken()).toBe("reg-token");
  });
});
