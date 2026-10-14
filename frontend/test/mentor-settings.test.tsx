/**
 * Phase 11G dashboard tests — AI mentor chat & read-only settings.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MentorChat } from "@/components/mentor/mentor-chat";
import { SettingsPanel } from "@/components/settings/settings-panel";
import { callBody, fetchQueue, jsonResponse, meFixture, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MentorChat", () => {
  it("posts the question and renders the returned answer", async () => {
    const fn = fetchQueue([jsonResponse({ answer: "Deterministic structure is authoritative." })]);
    render(<MentorChat />);
    expect(screen.getByTestId("mentor-empty")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("mentor-input"), { target: { value: "Why WAIT?" } });
    fireEvent.click(screen.getByTestId("mentor-send"));

    await waitFor(() => expect(screen.getByTestId("mentor-turn-mentor")).toBeInTheDocument());
    expect(screen.getByTestId("mentor-turn-user").textContent).toContain("Why WAIT?");
    expect(screen.getByTestId("mentor-turn-mentor").textContent).toContain("Deterministic structure");
    expect(String(fn.mock.calls[0][0])).toContain("/api/mentor/ask/");
    expect(await callBody(fn, 0)).toMatchObject({ question: "Why WAIT?" });
  });

  it("does not send an empty question", () => {
    const fn = fetchQueue([jsonResponse({ answer: "x" })]);
    render(<MentorChat />);
    fireEvent.click(screen.getByTestId("mentor-send"));
    expect(fn).not.toHaveBeenCalled();
  });

  it("surfaces a mentor error without inventing an answer", async () => {
    stubFetch().mockResolvedValue(jsonResponse({ error: "boom" }, 500));
    render(<MentorChat />);
    fireEvent.change(screen.getByTestId("mentor-input"), { target: { value: "hi" } });
    fireEvent.click(screen.getByTestId("mentor-send"));
    const err = await screen.findByTestId("error-state");
    expect(err.textContent).toContain("Mentor unavailable");
    expect(screen.queryByTestId("mentor-turn-mentor")).not.toBeInTheDocument();
  });
});

describe("SettingsPanel", () => {
  it("renders the account from /me and is honestly read-only", async () => {
    fetchQueue([jsonResponse(meFixture({ username: "naz", email: "naz@example.com" }))]);
    render(<SettingsPanel />);
    const panel = await screen.findByTestId("settings-panel");
    expect(panel.textContent).toContain("naz");
    expect(panel.textContent).toContain("naz@example.com");
    expect(panel.textContent).toContain("UTC");
    expect(screen.getByTestId("settings-readonly-note").textContent).toContain("not available yet");
  });

  it("shows the error state when the account cannot be loaded", async () => {
    stubFetch().mockRejectedValue(new Error("offline"));
    render(<SettingsPanel />);
    const err = await screen.findByTestId("error-state");
    expect(err.textContent).toContain("Account unavailable");
  });
});
