/**
 * Risk management panel tests (Phase 11D §7): request payload, honest
 * rendering of backend-computed numbers only, warning display, and the hard
 * requirement that no trade-execution controls exist.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RiskPanel } from "@/components/risk/risk-panel";
import { MarketProvider } from "@/components/layout/market-context";
import { callBody, fetchQueue, jsonResponse, stubFetch, tradePlanFixture } from "./helpers";

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

function renderPanel(onPlan?: (p: unknown) => void) {
  return render(
    <MarketProvider>
      <RiskPanel onPlan={onPlan} />
    </MarketProvider>,
  );
}

describe("RiskPanel", () => {
  it("posts the user's inputs to the trade-plan endpoint", async () => {
    const fn = fetchQueue([jsonResponse(tradePlanFixture())]);
    renderPanel();
    fireEvent.change(screen.getByTestId("risk-balance"), { target: { value: "25000" } });
    fireEvent.change(screen.getByTestId("risk-percent"), { target: { value: "0.5" } });
    fireEvent.change(screen.getByTestId("risk-entry"), { target: { value: "1.1002" } });
    fireEvent.change(screen.getByTestId("risk-sl"), { target: { value: "1.099" } });
    fireEvent.change(screen.getByTestId("risk-tp"), { target: { value: "1.103" } });
    fireEvent.click(screen.getByTestId("compute-plan"));

    await waitFor(() => expect(screen.getByTestId("risk-result")).toBeInTheDocument());
    const body = (await callBody(fn)) as Record<string, unknown>;
    expect(body).toMatchObject({
      symbol: "EURUSD",
      bias: "bullish",
      account_balance: 25000,
      risk_percent: 0.5,
      entry: 1.1002,
      sl: 1.099,
      tp: 1.103,
    });
  });

  it("renders only numbers the backend returned (missing → em dash)", async () => {
    fetchQueue([
      jsonResponse(tradePlanFixture({ entry_levels: [], sl: null, tp: null, rr: null, lot_size: null })),
    ]);
    renderPanel();
    fireEvent.click(screen.getByTestId("compute-plan"));
    await waitFor(() => expect(screen.getByTestId("risk-result")).toBeInTheDocument());
    expect(screen.getByTestId("plan-entry").textContent).toBe("—");
    expect(screen.getByTestId("plan-sl").textContent).toBe("—");
    expect(screen.getByTestId("plan-tp").textContent).toBe("—");
    expect(screen.getByTestId("plan-rr").textContent).toBe("—");
    expect(screen.getByTestId("plan-lots").textContent).toBe("—");
  });

  it("shows validated numbers when the backend computes them", async () => {
    fetchQueue([jsonResponse(tradePlanFixture())]);
    renderPanel();
    fireEvent.click(screen.getByTestId("compute-plan"));
    await waitFor(() => expect(screen.getByTestId("risk-result")).toBeInTheDocument());
    expect(screen.getByTestId("plan-entry").textContent).toBe("1.10020");
    expect(screen.getByTestId("plan-sl").textContent).toBe("1.09900");
    expect(screen.getByTestId("plan-tp").textContent).toBe("1.10300");
    expect(screen.getByTestId("plan-rr").textContent).toBe("2.40");
    expect(screen.getByTestId("plan-lots").textContent).toBe("0.08");
    expect(screen.getByTestId("plan-decision").textContent).toBe("BUY");
  });

  it("surfaces WAIT decisions with the backend's reasons and warnings", async () => {
    fetchQueue([
      jsonResponse(
        tradePlanFixture({
          decision: "WAIT",
          entry_levels: [1.1002],
          sl: 1.0995,
          tp: 1.103,
          rr: 0.3,
          warnings: ["RR below minimum (0.30 < 0.50)"],
          reasons: ["RR below minimum"],
        }),
      ),
    ]);
    renderPanel();
    fireEvent.click(screen.getByTestId("compute-plan"));
    await waitFor(() => expect(screen.getByTestId("plan-decision").textContent).toBe("WAIT"));
    expect(screen.getByTestId("plan-warnings").textContent).toContain("RR below minimum");
    expect(screen.getByTestId("plan-reasons").textContent).toContain("RR below minimum");
  });

  it("shows backend 400 validation errors verbatim", async () => {
    fetchQueue([
      jsonResponse({ error: "Invalid trade plan input", details: ["risk_percent must be > 0 and <= 10.0."], decision: "WAIT" }, 400),
    ]);
    renderPanel();
    fireEvent.click(screen.getByTestId("compute-plan"));
    const err = await screen.findByTestId("error-state");
    expect(err.textContent).toContain("risk_percent must be");
  });

  it("forwards the computed plan to the chart (levels 'when validated')", async () => {
    const onPlan = vi.fn();
    fetchQueue([jsonResponse(tradePlanFixture())]);
    renderPanel(onPlan);
    fireEvent.click(screen.getByTestId("compute-plan"));
    await waitFor(() => expect(onPlan).toHaveBeenCalledWith(expect.objectContaining({ decision: "BUY" })));
  });

  it("never renders trade-execution controls (analysis-only enforcement)", async () => {
    fetchQueue([jsonResponse(tradePlanFixture())]);
    renderPanel();
    fireEvent.click(screen.getByTestId("compute-plan"));
    await waitFor(() => expect(screen.getByTestId("risk-result")).toBeInTheDocument());
    const buttons = screen.getAllByRole("button").map((b) => b.textContent?.toLowerCase() ?? "");
    const forbidden = /execute|place order|buy now|sell now|open trade|submit order/;
    for (const label of buttons) {
      expect(label).not.toMatch(forbidden);
    }
  });
});
