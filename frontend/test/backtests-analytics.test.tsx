/**
 * Phase 11G dashboard tests — backtests & analytics.
 *
 * Recorded-only honesty: null metrics render as "—" (never 0), empty states
 * are explicit, and export streams the real `?format=` endpoint.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BacktestList } from "@/components/backtests/backtest-list";
import { AnalyticsPanel } from "@/components/analytics/analytics-panel";
import { backtestRunFixture, fetchQueue, journalPerformanceFixture, jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BacktestList", () => {
  it("renders recorded run metrics", async () => {
    fetchQueue([
      jsonResponse({
        count: 1,
        runs: [backtestRunFixture({ win_rate: 0.5, profit_factor: 1.35, net_profit: 525 })],
      }),
    ]);
    render(<BacktestList />);
    await waitFor(() => expect(screen.getAllByTestId("backtest-row")).toHaveLength(1));
    const row = screen.getByTestId("backtest-row");
    expect(row.textContent).toContain("EURUSD");
    expect(row.textContent).toContain("42");
    expect(row.textContent).toContain("50.0%");
    expect(row.textContent).toContain("+525.00");
    expect(row.textContent).toContain("2026-10-09 12:00");
  });

  it("renders an unknown metric as an em dash, never a fabricated zero", async () => {
    fetchQueue([
      jsonResponse({
        count: 1,
        runs: [backtestRunFixture({ win_rate: null, profit_factor: null, expectancy: null, net_profit: null })],
      }),
    ]);
    render(<BacktestList />);
    const row = await screen.findByTestId("backtest-row");
    expect(row.textContent).toContain("—");
    expect(row.textContent).not.toContain("0.00");
  });

  it("shows an honest empty state", async () => {
    fetchQueue([jsonResponse({ count: 0, runs: [] })]);
    render(<BacktestList />);
    expect(await screen.findByTestId("empty-state")).toBeInTheDocument();
  });

  it("shows the error state when unavailable", async () => {
    stubFetch().mockRejectedValue(new Error("network down"));
    render(<BacktestList />);
    const err = await screen.findByTestId("error-state");
    expect(err.textContent).toContain("Backtest history unavailable");
  });
});

describe("AnalyticsPanel", () => {
  it("renders the recorded aggregate and sample sizes", async () => {
    fetchQueue([jsonResponse(journalPerformanceFixture())]);
    render(<AnalyticsPanel />);
    const stats = await screen.findAllByTestId("analytics-stat");
    const text = stats.map((s) => s.textContent).join(" ");
    expect(text).toContain("60.0%"); // win rate
    expect(text).toContain("2.10"); // average rr
    expect(text).toContain("n=6"); // pnl sample on several stats
    expect(screen.getByTestId("analytics-note").textContent).toContain("null means");
  });

  it("renders null statistics as an em dash", async () => {
    fetchQueue([
      jsonResponse(
        journalPerformanceFixture({ win_rate: null, average_rr: null, total_pnl: null, expectancy: null, profit_factor: null, max_drawdown: null }),
      ),
    ]);
    render(<AnalyticsPanel />);
    const stats = await screen.findAllByTestId("analytics-stat");
    expect(stats.every((s) => s.textContent.includes("—"))).toBe(true);
  });

  it("shows an empty state when there are no entries", async () => {
    fetchQueue([
      jsonResponse(journalPerformanceFixture({ total_entries: 0, closed: 0, open: 0, outcomes: { WIN: 0, LOSS: 0, BE: 0, PENDING: 0 } })),
    ]);
    render(<AnalyticsPanel />);
    expect(await screen.findByTestId("empty-state")).toBeInTheDocument();
  });

  it("exports CSV through the real format endpoint", async () => {
    const fn = fetchQueue([
      jsonResponse(journalPerformanceFixture()),
      new Response("id,symbol\n1,EURUSD", { headers: { "Content-Type": "text/csv" } }),
    ]);
    render(<AnalyticsPanel />);
    await screen.findAllByTestId("analytics-stat");
    fireEvent.click(screen.getByTestId("export-csv"));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2));
    expect(String(fn.mock.calls[1][0])).toContain("/api/journal/export/?format=csv");
  });
});
