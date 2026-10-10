/**
 * Journal & analysis-history tests (Phase 11D §8): real fields only,
 * searchable history, owner-scoped list rendering, empty/error states.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HistoryList } from "@/components/history/history-list";
import { JournalPanel } from "@/components/journal/journal-panel";
import {
  analysisSummaryFixture,
  fetchQueue,
  journalEntryFixture,
  jsonResponse,
  stubFetch,
} from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("JournalPanel", () => {
  it("lists real recorded fields from the search endpoint", async () => {
    fetchQueue([
      jsonResponse({
        entries: [
          journalEntryFixture({ rr: 2.5, scenario_decision: "BUY", outcome: "WIN" }),
          journalEntryFixture({ id: "33333333-3333-3333-3333-333333333333", symbol: "GBPUSD" }),
        ],
      }),
    ]);
    render(<JournalPanel />);
    await waitFor(() => expect(screen.getAllByTestId("journal-row")).toHaveLength(2));
    const rows = screen.getAllByTestId("journal-row");
    expect(rows[0].textContent).toContain("EURUSD");
    expect(rows[0].textContent).toContain("BUY");
    expect(rows[0].textContent).toContain("WIN");
    expect(rows[0].textContent).toContain("2.50");
    // created timestamps are rendered in UTC
    expect(rows[0].textContent).toContain("2026-10-09 10:00");
  });

  it("search sends the query to the backend", async () => {
    const fn = fetchQueue([
      jsonResponse({ entries: [] }),
      jsonResponse({ entries: [journalEntryFixture()] }),
    ]);
    render(<JournalPanel />);
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByTestId("journal-search-input"), { target: { value: "sweep" } });
    fireEvent.click(screen.getByTestId("journal-search-button"));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2));
    expect(String(fn.mock.calls[1][0])).toContain("/api/journal/search/?q=sweep");
  });

  it("shows an honest empty state", async () => {
    fetchQueue([jsonResponse({ entries: [] })]);
    render(<JournalPanel />);
    expect(await screen.findByTestId("empty-state")).toBeInTheDocument();
  });

  it("shows the error state when search fails", async () => {
    fetchQueue([jsonResponse({ detail: "boom" }, 500)]);
    render(<JournalPanel />);
    const err = await screen.findByTestId("error-state");
    expect(err.textContent).toContain("Journal search failed");
  });

  it("saving a new entry posts the manual fields and refreshes the list", async () => {
    const fn = fetchQueue([
      jsonResponse({ entries: [] }), // initial
      jsonResponse({ id: "9" }, 201), // save
      jsonResponse({ entries: [journalEntryFixture({ notes: "new note" })] }), // refresh
    ]);
    render(<JournalPanel />);
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByTestId("journal-notes"), { target: { value: "new note" } });
    fireEvent.click(screen.getByTestId("journal-save"));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(3));
    const body = fn.mock.calls[1][1] as { body: string };
    expect(JSON.parse(body.body)).toMatchObject({ symbol: "EURUSD", notes: "new note", outcome: "PENDING" });
    await waitFor(() => expect(screen.getAllByTestId("journal-row")).toHaveLength(1));
  });
});

describe("HistoryList", () => {
  it("renders the owner's analyses with reopen links", async () => {
    fetchQueue([
      jsonResponse({
        analyses: [
          analysisSummaryFixture({ decision: "BUY" }),
          analysisSummaryFixture({ id: "44444444-4444-4444-4444-444444444444", symbol: "GBPUSD", decision: null }),
        ],
      }),
    ]);
    render(<HistoryList />);
    await waitFor(() => expect(screen.getAllByTestId("history-row")).toHaveLength(2));
    const rows = screen.getAllByTestId("history-row");
    expect(rows[0].textContent).toContain("BUY");
    expect(rows[1].textContent).toContain("GBPUSD");
    const link = screen.getAllByTestId("reopen-link")[0];
    expect(link.getAttribute("href")).toBe("/dashboard/analysis/22222222-2222-2222-2222-222222222222");
  });

  it("shows an empty state without fabricating rows", async () => {
    fetchQueue([jsonResponse({ analyses: [] })]);
    render(<HistoryList />);
    expect(await screen.findByTestId("empty-state")).toBeInTheDocument();
  });

  it("shows the error state with retry when history is unreachable", async () => {
    stubFetch().mockRejectedValue(new Error("network down"));
    render(<HistoryList />);
    const err = await screen.findByTestId("error-state");
    expect(err.textContent).toContain("History unavailable");
  });
});
