import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./test/setup.ts"],
    include: ["test/**/*.test.{ts,tsx}"],
    css: false,
    restoreMocks: true,
    // The workspace path contains spaces; the default `forks` pool fails to
    // spawn workers on Windows in that case — `threads` is unaffected. Worker
    // startup on this machine can take tens of seconds, and Vitest's start
    // timeout is a hardcoded 60s, so concurrency is capped to avoid a spawn
    // pileup when many test files run in parallel.
    pool: "threads",
    maxWorkers: 4,
    testTimeout: 20_000,
    hookTimeout: 20_000,
  },
});
