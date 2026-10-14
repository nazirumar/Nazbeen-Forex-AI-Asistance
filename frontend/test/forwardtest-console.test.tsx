/**
 * Phase 11G dashboard tests — forward-test console (§9/§10).
 *
 * Honesty: observations are labelled simulated, null levels render as "—", a
 * failed run shows its safe error, and there are no live-execution controls.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ForwardTestConsole } from "@/components/forwardtests/forwardtest-console";
import {
  forwardTestObservationFixture,
  forwardTestRunFixture,
  fetchQueue,
  jsonResponse,
  stubFetch,
} from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

function startedQueue(obsOver = {}, runOver = {}) {
  return fetchQueue([
    jsonResponse({ run: forwardTestRunFixture(runOver) }),
    jsonResponse({ count: 1, observations: [forwardTestObservationFixture(obsOver)] }),
  ]);
}

describe("ForwardTestConsole", () => {
  it("renders the configuration form with defaults", () => {
    stubFetch().mockResolvedValue(jsonResponse({}));
    render(<ForwardTestConsole />);
    expect(screen.getByTestId("ft-config-form")).toBeInTheDocument();
    expect(screen.getByTestId("ft-symbol")).toHaveValue("EURUSD");
    expect(screen.getByTestId("ft-timeframe")).toHaveValue("M15");
  });

  it("starts a simulated forward test and shows its observation", async () => {
    const fn = startedQueue();
    render(<ForwardTestConsole />);
    fireEvent.click(screen.getByTestId("ft-start"));

    await waitFor(() => expect(screen.getByTestId("ft-result")).toBeInTheDocument());
    expect(String(fn.mock.calls[0][0])).toContain("/api/forwardtests/runs/");
    expect(screen.getByTestId("ft-status").textContent?.toLowerCase()).toContain("active");
    expect(screen.getByTestId("ft-simulated").textContent).toContain("simulated");
    expect(screen.getByTestId("ft-source").textContent).toContain("mock");
    expect(screen.getAllByTestId("ft-obs-row")).toHaveLength(1);
  });

  it("renders a WAIT observation with null levels as an em dash", async () => {
    startedQueue({ decision: "WAIT", entry: null, sl: null, tp: null, rr: null, outcome: "PENDING", outcome_r: null });
    render(<ForwardTestConsole />);
    fireEvent.click(screen.getByTestId("ft-start"));
    await waitFor(() => expect(screen.getByTestId("ft-obs-row")).toBeInTheDocument());
    const row = screen.getByTestId("ft-obs-row");
    expect(row.textContent).toContain("WAIT");
    expect(row.textContent).toContain("—");
    expect(row.textContent).toContain("PENDING");
  });

  it("observes a run and refreshes the recorded rows", async () => {
    const fn = fetchQueue([
      jsonResponse({ run: forwardTestRunFixture() }),
      jsonResponse({ count: 1, observations: [forwardTestObservationFixture()] }),
      jsonResponse({ run: forwardTestRunFixture({ observations_count: 1 }) }),
      jsonResponse({ count: 1, observations: [forwardTestObservationFixture()] }),
    ]);
    render(<ForwardTestConsole />);
    fireEvent.click(screen.getByTestId("ft-start"));
    await waitFor(() => expect(screen.getByTestId("ft-observe")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("ft-observe"));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(4));
    expect(String(fn.mock.calls[2][0])).toContain("/observe/");
  });

  it("journals an observation through the typed endpoint", async () => {
    const fn = fetchQueue([
      jsonResponse({ run: forwardTestRunFixture() }),
      jsonResponse({ count: 1, observations: [forwardTestObservationFixture()] }),
      jsonResponse({ journal_entry_id: "99999999-9999-9999-9999-999999999999", source: "forward_test" }, 201),
    ]);
    render(<ForwardTestConsole />);
    fireEvent.click(screen.getByTestId("ft-start"));
    await waitFor(() => expect(screen.getByTestId("ft-journal")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ft-journal"));
    const msg = await screen.findByTestId("ft-journal-msg");
    expect(msg.textContent).toContain("forward_test");
    expect(String(fn.mock.calls[2][0])).toContain("/api/forwardtests/observations/");
    expect(String(fn.mock.calls[2][0])).toContain("/journal/");
  });

  it("stops an active run", async () => {
    const fn = fetchQueue([
      jsonResponse({ run: forwardTestRunFixture() }),
      jsonResponse({ count: 0, observations: [] }),
      jsonResponse({ run: forwardTestRunFixture({ status: "stopped" }) }),
    ]);
    render(<ForwardTestConsole />);
    fireEvent.click(screen.getByTestId("ft-start"));
    await waitFor(() => expect(screen.getByTestId("ft-stop")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ft-stop"));
    await waitFor(() =>
      expect(screen.getByTestId("ft-status").textContent?.toLowerCase()).toContain("stopped"),
    );
    expect(String(fn.mock.calls[2][0])).toContain("/stop/");
  });

  it("shows a failed run's safe error", async () => {
    fetchQueue([
      jsonResponse({
        run: forwardTestRunFixture({ status: "failed", error: "Not enough candles to observe." }),
      }),
      jsonResponse({ count: 0, observations: [] }),
    ]);
    render(<ForwardTestConsole />);
    fireEvent.click(screen.getByTestId("ft-start"));
    const failed = await screen.findByTestId("ft-failed");
    expect(failed.textContent).toContain("Not enough candles");
  });

  it("exposes no live-execution controls", () => {
    stubFetch().mockResolvedValue(jsonResponse({}));
    render(<ForwardTestConsole />);
    const buttons = screen.getAllByRole("button").map((b) => b.textContent?.toLowerCase() ?? "");
    expect(buttons.some((t) => /place order|execute|buy now|sell now|live/.test(t))).toBe(false);
  });
});
