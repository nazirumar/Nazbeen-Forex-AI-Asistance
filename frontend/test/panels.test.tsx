/**
 * Multi-timeframe panel & shared state components (Phase 11D §3/§6).
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MtfPanel } from "@/components/analysis/mtf-panel";
import { DataSourceBadge, EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { structureFixture } from "./helpers";
import type { MtfView } from "@/lib/types";

function mtf(over: Partial<MtfView> = {}): MtfView {
  return {
    H1: "BULLISH",
    M15: "BULLISH",
    M5: "BEARISH",
    M1: "NEUTRAL",
    conflicts: [],
    ...over,
  };
}

describe("MtfPanel", () => {
  it("renders bullish/bearish/neutral states from the backend verdicts", () => {
    render(<MtfPanel data={structureFixture({ mtf: mtf() })} loading={false} error={null} />);
    expect(screen.getByTestId("mtf-H1").textContent).toContain("Bullish");
    expect(screen.getByTestId("mtf-M5").textContent).toContain("Bearish");
    expect(screen.getByTestId("mtf-M1").textContent).toContain("Neutral");
    expect(screen.getByTestId("mtf-M15").textContent).toContain("Bullish");
  });

  it("shows an unavailable timeframe as Unavailable — never as NEUTRAL", () => {
    render(
      <MtfPanel
        data={structureFixture({ mtf: mtf({ H1: null, M5: null }) })}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByTestId("mtf-H1").textContent).toContain("Unavailable");
    expect(screen.getByTestId("mtf-M5").textContent).toContain("Unavailable");
    expect(screen.getByTestId("mtf-H1").textContent).not.toContain("Neutral");
  });

  it("surfaces real conflicts between timeframes", () => {
    render(
      <MtfPanel
        data={structureFixture({ mtf: mtf({ conflicts: ["H1 BULLISH vs M5 BEARISH"] }) })}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByTestId("mtf-conflicts").textContent).toContain("H1 BULLISH vs M5 BEARISH");
  });

  it("states there are no conflicts explicitly when the list is empty", () => {
    render(<MtfPanel data={structureFixture({ mtf: mtf() })} loading={false} error={null} />);
    expect(screen.getByTestId("mtf-conflicts").textContent).toContain("No conflicts");
  });

  it("shows the mock-data label when the source is mock", () => {
    render(<MtfPanel data={structureFixture({ data_source: "mock" })} loading={false} error={null} />);
    expect(screen.getByTestId("data-source-badge").textContent).toContain("Mock data");
  });

  it("renders loading, error and empty states", () => {
    const { rerender } = render(<MtfPanel data={null} loading={true} error={null} />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    rerender(<MtfPanel data={null} loading={false} error={new Error("offline")} />);
    expect(screen.getByTestId("error-state").textContent).toContain("offline");
    rerender(<MtfPanel data={null} loading={false} error={null} />);
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
  });
});

describe("shared state components", () => {
  it("LoadingState announces politely for screen readers", () => {
    render(<LoadingState label="Loading chart…" />);
    const el = screen.getByTestId("loading-state");
    expect(el).toHaveAttribute("role", "status");
    expect(el.textContent).toContain("Loading chart…");
  });

  it("EmptyState shows title and hint", () => {
    render(<EmptyState title="Nothing here" hint="Upload to begin" />);
    expect(screen.getByTestId("empty-state").textContent).toContain("Nothing here");
    expect(screen.getByTestId("empty-state").textContent).toContain("Upload to begin");
  });

  it("ErrorState renders the real error message and an optional retry", () => {
    const { rerender } = render(<ErrorState error={new Error("HTTP 503")} onRetry={() => undefined} />);
    expect(screen.getByTestId("error-state").textContent).toContain("HTTP 503");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    rerender(<ErrorState error={"plain failure"} />);
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("DataSourceBadge distinguishes mock from real data", () => {
    const { rerender } = render(<DataSourceBadge source="mock" />);
    expect(screen.getByTestId("data-source-badge").textContent).toContain("Mock data");
    rerender(<DataSourceBadge source="mt5" />);
    expect(screen.getByTestId("data-source-badge").textContent).toContain("MT5 data");
    rerender(<DataSourceBadge source={null} />);
    expect(screen.queryByTestId("data-source-badge")).toBeNull();
  });
});
