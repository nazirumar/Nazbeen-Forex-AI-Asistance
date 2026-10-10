/**
 * Screenshot upload workspace tests (Phase 11D §5): type/size validation,
 * preview, multipart submission with the current symbol/timeframe, processing
 * states and honest rendering of the backend result.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UploadPanel } from "@/components/analysis/upload-panel";
import { MarketProvider } from "@/components/layout/market-context";
import { analysisResultFixture, fetchQueue, jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

function renderPanel() {
  return render(
    <MarketProvider>
      <UploadPanel />
    </MarketProvider>,
  );
}

function pngFile(name = "chart.png", type = "image/png"): File {
  return new File(["fake-png"], name, { type });
}

async function pick(file: File | null) {
  const input = screen.getByTestId("file-input") as HTMLInputElement;
  fireEvent.change(input, { target: { files: file ? [file] : [] } });
}

describe("UploadPanel", () => {
  it("rejects non-PNG/JPEG files client-side with a clear message", async () => {
    stubFetch();
    renderPanel();
    await pick(pngFile("chart.gif", "image/gif"));
    expect(await screen.findByTestId("upload-rejection")).toHaveTextContent("Only PNG or JPEG");
    expect(screen.getByTestId("submit-analysis")).toBeDisabled();
  });

  it("rejects files above the backend's 5MB limit", async () => {
    stubFetch();
    renderPanel();
    const big = pngFile();
    Object.defineProperty(big, "size", { value: 6 * 1024 * 1024 });
    await pick(big);
    expect(await screen.findByTestId("upload-rejection")).toHaveTextContent("Max 5MB");
  });

  it("previews the chosen image", async () => {
    stubFetch();
    renderPanel();
    await pick(pngFile());
    await waitFor(() => expect(screen.getByTestId("upload-preview")).toBeInTheDocument());
    const img = screen.getByAltText("Screenshot preview") as HTMLImageElement;
    expect(img.getAttribute("src")).toMatch(/^blob:/);
  });

  it("submits multipart form data with image + current symbol/timeframe", async () => {
    const fn = fetchQueue([
      jsonResponse(
        { analysis_id: "id-1", screenshot_stored: true, result: analysisResultFixture() },
        201,
      ),
    ]);
    renderPanel();
    await pick(pngFile());
    fireEvent.click(screen.getByTestId("submit-analysis"));

    await waitFor(() => expect(screen.getByTestId("analysis-result")).toBeInTheDocument());
    const init = fn.mock.calls[0][1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect((form.get("image") as File).name).toBe("chart.png");
    expect(form.get("symbol")).toBe("EURUSD"); // default market selection
    expect(form.get("timeframe")).toBe("M15");
  });

  it("shows the processing state while the analysis request is running", async () => {
    let resolveFetch: (r: Response) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((res) => {
            resolveFetch = res;
          }),
      ),
    );
    renderPanel();
    await pick(pngFile());
    fireEvent.click(screen.getByTestId("submit-analysis"));
    expect(await screen.findByTestId("loading-state")).toBeInTheDocument();
    resolveFetch(
      jsonResponse({ screenshot_stored: false, result: analysisResultFixture() }, 201),
    );
    await waitFor(() => expect(screen.getByTestId("analysis-result")).toBeInTheDocument());
  });

  it("renders the verdict, evidence and disagreements exactly as returned", async () => {
    fetchQueue([
      jsonResponse(
        { screenshot_stored: true, result: analysisResultFixture({ decision: "SELL", data_synchronized: false }) },
        201,
      ),
    ]);
    renderPanel();
    await pick(pngFile());
    fireEvent.click(screen.getByTestId("submit-analysis"));

    await waitFor(() => expect(screen.getByTestId("analysis-result")).toBeInTheDocument());
    expect(screen.getByTestId("decision-badge").textContent).toBe("SELL SCENARIO");
    expect(screen.getByTestId("sync-badge").textContent).toContain("not synchronized");
    expect(screen.getByTestId("evidence-item").textContent).toContain("deterministic");
    expect(screen.getByTestId("disagreement-item").textContent).toContain("bias");
    expect(screen.getByTestId("uncertainty-item").textContent).toContain("Spread not provided");
  });

  it("renders WAIT without inventing levels that are absent", async () => {
    fetchQueue([
      jsonResponse(
        {
          screenshot_stored: false,
          result: analysisResultFixture({ decision: "WAIT", entry_levels: [], sl: null, tp: null, risk_reward: null }),
        },
        201,
      ),
    ]);
    renderPanel();
    await pick(pngFile());
    fireEvent.click(screen.getByTestId("submit-analysis"));
    await waitFor(() => expect(screen.getByTestId("decision-badge").textContent).toBe("WAIT"));
    expect(screen.queryByTestId("result-levels")).toBeNull();
  });

  it("surfaces backend 400 rejections (audit-H-01 strict validation)", async () => {
    fetchQueue([
      jsonResponse({ error: "Invalid image upload", details: ["Unsupported file extension: .txt"] }, 400),
    ]);
    renderPanel();
    await pick(pngFile());
    fireEvent.click(screen.getByTestId("submit-analysis"));
    const err = await screen.findByTestId("error-state");
    expect(err.textContent).toContain("Upload rejected");
    expect(err.textContent).toContain("Unsupported file extension");
    expect(screen.queryByTestId("analysis-result")).toBeNull();
  });
});
