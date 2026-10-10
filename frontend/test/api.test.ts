/**
 * API helper tests (Phase 11D §2): token attachment, DRF error extraction,
 * session-expiry behaviour (401 → token cleared + event), and multipart
 * passthrough for screenshot uploads.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  api,
  ApiError,
  apiBlob,
  AUTH_EXPIRED_EVENT,
  getToken,
  setToken,
} from "@/lib/api";
import { authHeaders, callBody, fetchQueue, jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("api()", () => {
  it("attaches the stored token as an Authorization header", async () => {
    const fn = fetchQueue([jsonResponse({ ok: true })]);
    setToken("tok-123");
    await api("/api/auth/me/");
    expect(authHeaders(fn)[0]).toBe("Token tok-123");
    const url = fn.mock.calls[0][0] as string;
    expect(url.endsWith("/api/auth/me/")).toBe(true);
  });

  it("sends JSON bodies as application/json", async () => {
    const fn = fetchQueue([jsonResponse({ token: "t" })]);
    await api("/api/auth/login/", { method: "POST", body: { username: "u", password: "p" } });
    const init = fn.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(await callBody(fn)).toEqual({ username: "u", password: "p" });
  });

  it("does not force Content-Type for FormData (browser sets the boundary)", async () => {
    const fn = fetchQueue([jsonResponse({ result: {} })]);
    const form = new FormData();
    form.append("image", new File(["x"], "a.png", { type: "image/png" }));
    await api("/api/analysis/upload/", { method: "POST", formData: form });
    const init = fn.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("surfaces DRF detail messages as ApiError with the real status", async () => {
    stubFetch().mockResolvedValue(jsonResponse({ detail: "Invalid credentials." }, 400));
    await expect(api("/api/auth/login/", { method: "POST", body: {} })).rejects.toMatchObject({
      status: 400,
      message: "Invalid credentials.",
    });
  });

  it("exposes field errors for form rendering", async () => {
    stubFetch().mockResolvedValue(
      jsonResponse({ password: ["This password is too common."], username: ["Required."] }, 400),
    );
    const err = await api("/api/auth/register/", { method: "POST", body: {} }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).fields).toEqual({
      password: ["This password is too common."],
      username: ["Required."],
    });
  });

  it("survives non-JSON error bodies without crashing", async () => {
    stubFetch().mockResolvedValue(new Response("<html>502</html>", { status: 502 }));
    const err = await api("/api/mt5/status/").catch((e) => e);
    expect((err as ApiError).status).toBe(502);
    expect((err as ApiError).message.length).toBeGreaterThan(0);
  });

  describe("session expiry (401)", () => {
    it("clears the token and emits the auth-expired event", async () => {
      const fn = fetchQueue([jsonResponse({ detail: "Invalid token." }, 401)]);
      setToken("expired-token");
      const onExpired = vi.fn();
      window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);

      await expect(api("/api/analysis/")).rejects.toBeInstanceOf(ApiError);
      expect(getToken()).toBeNull();
      expect(onExpired).toHaveBeenCalledTimes(1);

      window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it("does not fire the expiry event for failed logins (401/400 = bad credentials)", async () => {
      setToken(null);
      const onExpired = vi.fn();
      window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
      fetchQueue([jsonResponse({ detail: "Invalid credentials." }, 401)]);
      await expect(api("/api/auth/login/", { method: "POST", body: {} })).rejects.toBeInstanceOf(
        ApiError,
      );
      expect(onExpired).not.toHaveBeenCalled();
      window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
    });
  });
});

describe("apiBlob()", () => {
  it("returns the binary body with the token attached", async () => {
    setToken("tok-blob");
    const fn = fetchQueue([new Response(new Blob(["png-bytes"]), { status: 200 })]);
    const blob = await apiBlob("/api/analysis/x/screenshot/");
    expect(blob.size).toBeGreaterThan(0);
    expect(authHeaders(fn)[0]).toBe("Token tok-blob");
  });

  it("throws ApiError on 404 (screenshot not stored)", async () => {
    fetchQueue([jsonResponse({ detail: "Not found" }, 404)]);
    await expect(apiBlob("/api/analysis/x/screenshot/")).rejects.toMatchObject({ status: 404 });
  });
});
