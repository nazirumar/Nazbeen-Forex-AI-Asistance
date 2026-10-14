/**
 * Phase 11G dashboard tests — backtest console (§7).
 *
 * Honesty: null metrics render as "—", failed runs show their safe error, the
 * progress display never invents a percentage, and there are no live-execution
 * controls anywhere.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BacktestConsole } from "@/components/backtests/backtest-console";
import {
  backtestMetricsFixture,
  backtestRunFixture,
  backtestTradeFixture,
  callBody,
  equityPointsFixture,
  fetchQueue,
  jsonResponse,
  stubFetch,
} from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

function resultsQueue(runOver = {}, metricsOver = {}) {
  return fetchQueue([
    jsonResponse({ run: backtestRunFixture(runOver) }),
    jsonResponse({ metrics: backtestMetricsFixture(metricsOver), status: "completed" }),
    jsonResponse({ count: 1, trades: [backtestTradeFixture()] }),
    jsonResponse({ points: equityPointsFixture() }),
  ]);
}

describe("BacktestConsole", () => {
  it("renders the configuration form", () => {
    stubFetch().mockResolvedValue(jsonResponse({}));
    render(<BacktestConsole />);
    expect(screen.getByTestId("bt-config-form")).toBeInTheDocument();
    expect(screen.getByTestId("bt-symbol")).toHaveValue("EURUSD");
    expect(screen.getByTestId("bt-timeframe")).toHaveValue("M15");
  });

  it("submits the configuration and renders stored results", async () => {
    const fn = resultsQueue();
    render(<BacktestConsole />);
    fireEvent.click(screen.getByTestId("bt-start"));

    await waitFor(() => expect(screen.getAllByTestId("bt-metric").length).toBeGreaterThan(0));
    const body = (await callBody(fn, 0)) as Record<string, unknown>;
    expect(body.symbol).toBe("EURUSD");
    expect(typeof body.count).toBe("number");
    expect(String(fn.mock.calls[0][0])).toContain("/api/backtests/runs/");

    expect(screen.getByTestId("bt-status").textContent?.toLowerCase()).toContain("completed");
    const text = screen.getAllByTestId("bt-metric").map((n) => n.textContent).join(" ");
    expect(text).toContain("+100.00"); // net profit
    expect(text).toContain("50.0%"); // win rate
    expect(screen.getByTestId("bt-equity")).toBeInTheDocument();
    expect(screen.getAllByTestId("bt-trade-row")).toHaveLength(1);
  });

  it("renders null metrics as an em dash, never a fabricated zero", async () => {
    resultsQueue(
      {},
      { win_rate: null, profit_factor: null, expectancy: null, average_realized_r: null },
    );
    render(<BacktestConsole />);
    fireEvent.click(screen.getByTestId("bt-start"));
    await waitFor(() => expect(screen.getAllByTestId("bt-metric").length).toBeGreaterThan(0));
    const text = screen.getAllByTestId("bt-metric").map((n) => n.textContent).join(" ");
    expect(text).toContain("—");
    expect(text).not.toContain("0.00%");
  });

  it("shows a failed run's safe error and no metrics", async () => {
    fetchQueue([
      jsonResponse({
        run: backtestRunFixture({
          status: "failed",
          error: "Not enough historical candles to backtest (5 < 40).",
        }),
      }),
    ]);
    render(<BacktestConsole />);
    fireEvent.click(screen.getByTestId("bt-start"));
    const failed = await screen.findByTestId("bt-failed");
    expect(failed.textContent).toContain("Not enough historical candles");
    expect(screen.queryByTestId("bt-metric")).toBeNull();
  });

  it("surfaces a validation error from the backend", async () => {
    fetchQueue([
      jsonResponse({ error: "Invalid configuration", details: ["timeframe must be one of M1, M5, M15, H1."] }, 400),
    ]);
    render(<BacktestConsole />);
    fireEvent.click(screen.getByTestId("bt-start"));
    const err = await screen.findByTestId("error-state");
    expect(err.textContent).toContain("timeframe must be one of");
  });

  it("inspects a selected trade", async () => {
    resultsQueue();
    render(<BacktestConsole />);
    fireEvent.click(screen.getByTestId("bt-start"));
    await waitFor(() => expect(screen.getByTestId("bt-trade-row")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("bt-trade-row"));
    const detail = screen.getByTestId("bt-trade-detail");
    expect(detail.textContent).toContain("LONG");
    expect(detail.textContent).toContain("take_profit");
  });

  it("exports through the real per-run export endpoint", async () => {
    const fn = fetchQueue([
      jsonResponse({ run: backtestRunFixture() }),
      jsonResponse({ metrics: backtestMetricsFixture(), status: "completed" }),
      jsonResponse({ count: 1, trades: [backtestTradeFixture()] }),
      jsonResponse({ points: equityPointsFixture() }),
      new Response("index,side\n0,LONG", { headers: { "Content-Type": "text/csv" } }),
    ]);
    render(<BacktestConsole />);
    fireEvent.click(screen.getByTestId("bt-start"));
    await waitFor(() => expect(screen.getByTestId("bt-export-csv")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("bt-export-csv"));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(5));
    expect(String(fn.mock.calls[4][0])).toContain(
      "/api/backtests/runs/55555555-5555-5555-5555-555555555555/export/?format=csv",
    );
  });

  it("exposes no live-execution controls", () => {
    stubFetch().mockResolvedValue(jsonResponse({}));
    render(<BacktestConsole />);
    const buttons = screen.getAllByRole("button").map((b) => b.textContent?.toLowerCase() ?? "");
    expect(buttons.some((t) => /place order|execute|buy now|sell now|live/.test(t))).toBe(false);
  });
});
