# MT5 Worker Setup & Integration Notes (Windows)

This document describes how the Windows-based MT5 connector worker integrates with the Django backend.

## Purpose

The MT5 worker runs on the Windows host alongside the MetaTrader 5 desktop terminal. Because the `MetaTrader5` Python package depends on the Windows MT5 terminal, the backend (which may run in Docker/Linux) does NOT import the MT5 package directly — instead it uses the provider abstraction (`MarketDataProvider`) that can call the worker over HTTP, or use the Mock adapter for offline tests.

## Phase 2 Implementation (current)

Phase 2 implements the Django-side provider abstraction and API endpoints:

- `MarketDataProvider` (interface) — defines connect/status/symbols/candles/tick.
- `MockMarketDataProvider` — deterministic, clearly labeled `mode: "mock"`; used when `MT5_USE_MOCK=true` (default in dev/tests).
- `MT5MarketDataProvider` — wraps the `MetaTrader5` Python package for Windows runtime; has safe retry/reconnection logic and validates OHLC. It is intended to be used by the Windows worker process (or can be embedded in the worker).
- `Factory` — selects provider based on `MT5_USE_MOCK`.
- API endpoints (require auth): `GET /api/mt5/status/`, `GET /api/mt5/symbols/`, `GET /api/mt5/candles/`, `GET /api/mt5/tick/`.
- All responses include `data_source` (`mock` or `mt5`) and UTC-normalized timestamps (`Z` suffix).

## Windows Worker (future integration)

A dedicated `mt5_worker/` package is planned to run as a Windows service/console app that:
1. Loads MT5 credentials from environment (path/login/server/password).
2. Calls `MetaTrader5.initialize()` and maintains connection (reconnect with backoff).
3. Exposes authenticated HTTP endpoints returning JSON with UTC timestamps.
4. Validates OHLC, detects missing candles/stale data, handles market closures.
5. Never logs secrets.

## Environment variables

- `MT5_USE_MOCK` (bool, default true) — use Mock provider; set to false only when MT5 terminal is available.
- `MT5_PATH`, `MT5_LOGIN`, `MT5_SERVER`, `MT5_PASSWORD` — optional for local terminal auth.
- `MT5_TIMEOUT_SEC`, `MT5_RETRY_MAX`, `MT5_RETRY_BACKOFF` — retry/reconnect tuning.

## Usage

- Development/tests: leave `MT5_USE_MOCK=true` (no MT5 required; all tests pass).
- Windows with MT5 terminal: set `MT5_USE_MOCK=false` and configure credentials; ensure terminal is logged in and allowed to provide historical data.

## Safety notes

- Analysis-only (no order execution).
- Mock data is always clearly labeled.
- Timestamps normalized to UTC.
- Errors are surfaced safely without leaking credentials.
- Reconnection/retry implemented with bounded backoff.