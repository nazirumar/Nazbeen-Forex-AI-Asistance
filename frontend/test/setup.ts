/**
 * Vitest global setup (Phase 11D).
 *
 * jsdom lacks a few browser APIs the dashboard relies on; they are stubbed
 * here with realistic minimal behaviour so component tests exercise the real
 * code paths (chart resize observation, object-URL previews).
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

// ResizeObserver: record observed elements; no-op lifecycle.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
vi.stubGlobal("ResizeObserver", ResizeObserverStub);

// Object URLs (screenshot preview / reopened image).
let urlCounter = 0;
if (typeof URL.createObjectURL !== "function") {
  URL.createObjectURL = () => `blob:vitest/${++urlCounter}`;
  URL.revokeObjectURL = () => undefined;
}
