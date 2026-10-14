/**
 * Primary setup checklist rendering tests (Phase 11E WP6).
 *
 * The checklist must mirror the backend's deterministic steps exactly and must
 * never imply a setup exists when `complete` is false — including the honest
 * empty/insufficient state when there is no checklist at all.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SetupChecklist } from "@/components/analysis/setup-checklist";
import { setupFixture, setupStepFixture } from "./helpers";

describe("SetupChecklist", () => {
  it("renders the model name and every step with its real status", () => {
    render(<SetupChecklist setup={setupFixture()} />);
    expect(screen.getByTestId("setup-model").textContent).toContain("ict_primary_setup_v1");
    const steps = screen.getByTestId("setup-steps").querySelectorAll("li");
    expect(steps).toHaveLength(7);
    expect(screen.getByTestId("setup-step-bias_confirmed").textContent).toContain("Bias confirmed");
    expect(screen.getByTestId("setup-step-bias_confirmed").textContent).toContain("Satisfied");
    expect(screen.getByTestId("setup-step-liquidity_swept").textContent).toContain("Missing");
    expect(screen.getByTestId("setup-step-m1_confirmed").textContent).toContain("Unavailable");
  });

  it("states that no complete setup exists when complete is false", () => {
    render(<SetupChecklist setup={setupFixture({ complete: false, decision: "WAIT" })} />);
    expect(screen.getByTestId("setup-incomplete").textContent).toContain("No complete setup");
    expect(screen.getByTestId("setup-state").textContent).toContain("Incomplete");
    expect(screen.getByTestId("setup-state").textContent).not.toContain("Complete ·");
    // The steps are still shown so the user can see exactly where it stopped.
    expect(screen.getByTestId("setup-steps")).toBeInTheDocument();
  });

  it("shows the decision and hides the incomplete warning for a complete setup", () => {
    render(<SetupChecklist setup={setupFixture({ complete: true, decision: "BUY", blocked_by: [] })} />);
    expect(screen.getByTestId("setup-state").textContent).toContain("Complete");
    expect(screen.getByTestId("setup-state").textContent).toContain("BUY");
    expect(screen.queryByTestId("setup-incomplete")).toBeNull();
  });

  it("renders the backend's blocked_by reasons verbatim", () => {
    render(<SetupChecklist setup={setupFixture({ blocked_by: ["m5_conflict", "stale_chain"] })} />);
    const blocked = screen.getByTestId("setup-blocked-by");
    expect(blocked.textContent).toContain("m5_conflict");
    expect(blocked.textContent).toContain("stale_chain");
  });

  it("shows an explicit no-setup/insufficient state when there is no setup", () => {
    render(<SetupChecklist setup={null} />);
    expect(screen.getByTestId("setup-empty").textContent).toContain("No setup yet");
    expect(screen.getByTestId("setup-empty").textContent).toContain("Insufficient");
    expect(screen.queryByTestId("setup-steps")).toBeNull();
    expect(screen.getByTestId("setup-state").textContent).toContain("Incomplete");
  });

  it("shows the empty state when the backend returns an empty step list", () => {
    render(<SetupChecklist setup={setupFixture({ steps: [], blocked_by: [] })} />);
    expect(screen.getByTestId("setup-empty").textContent).toContain("No setup yet");
    expect(screen.queryByTestId("setup-steps")).toBeNull();
  });

  it("renders a step's confirming timestamp when present", () => {
    render(
      <SetupChecklist
        setup={setupFixture({
          steps: [
            setupStepFixture({
              key: "bias_confirmed",
              label: "Bias confirmed",
              status: "satisfied",
              time: "2026-01-01T00:15:00Z",
            }),
          ],
        })}
      />,
    );
    expect(screen.getByTestId("setup-step-bias_confirmed").textContent).toContain("2026-01-01T00:15:00Z");
  });

  it("never renders trade-execution controls (analysis-only enforcement)", () => {
    render(<SetupChecklist setup={setupFixture({ complete: true, decision: "BUY", blocked_by: [] })} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
