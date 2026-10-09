# MASTER SPECIFICATION — Nazbeen Forex AI Asistance

> This is the canonical, authoritative specification for the project.
> Every development phase MUST start by reading this file and `docs/PROJECT_PROGRESS.md`.
> This file is derived verbatim from the project owner's master project prompt.
> Do not weaken or silently reinterpret any requirement below.

## 1. Project identity

- Application name: **Nazbeen Forex AI Asistance**
- Internal package name: `nazbeen_forex_ai`
- Application type: AI-powered Forex market analysis and decision-support platform
- Initial market: EURUSD
- Primary analysis timeframe: M15
- Entry confirmation timeframe: M1
- Additional context timeframes: H1 and M5
- Trading methodology: ICT, Smart Money Concepts and price action
- Initial execution mode: **Analysis-only**
- Initial environment: Windows 11 development with MT5 desktop terminal

Use professional software architecture and modern, maintainable engineering practices.

## 2. Required technology stack

### Backend

- Python 3.12 (or another explicitly justified stable compatible version)
- Django
- Django REST Framework
- Django Channels
- Celery
- Redis
- PostgreSQL
- `MetaTrader5` Python package
- pandas
- NumPy
- scikit-learn
- LightGBM where useful
- LangGraph
- Pydantic for structured AI outputs
- pytest and pytest-django

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- Responsive dashboard
- WebSocket updates
- Professional chart visualization

### AI

- Configurable vision-capable LLM provider
- Configurable text reasoning provider
- LangGraph orchestration
- Structured outputs and validation
- PostgreSQL with optional pgvector for semantic memory

### Infrastructure

- Docker Compose for compatible services
- Windows-hosted MT5 worker
- Environment-based configuration
- Structured logging
- Health checks
- Automated tests
- CI pipeline

**Constraint:** Do not assume that the `MetaTrader5` Python package works inside a Linux Docker
container. Design a separate Windows MT5 connector that communicates securely with the backend.

## 3. Core system requirements

### A. Screenshot analysis

Users must be able to upload screenshots from TradingView or MetaTrader 5.

The AI must:

- Inspect candlestick structure.
- Identify the visible instrument and timeframe where possible.
- Detect potential support and resistance.
- Identify candidate liquidity levels.
- Identify potential BOS, CHOCH, MSS, displacement, FVGs and order blocks.
- Explain bullish and bearish scenarios.
- Report uncertainty.
- Identify missing evidence.
- Compare screenshot findings with live or historical MT5 data.

Rules:

- Never invent exact price levels when the screenshot does not provide sufficient information.
- If the screenshot timestamp is unknown, do not assume that current MT5 data represents the same
  chart state.

### B. MT5 market data

Build a reliable MetaTrader 5 connector supporting:

- Connection status
- Broker and server metadata
- Symbol discovery
- Symbol suffix handling
- Historical OHLCV candles
- M1, M5, M15 and H1 data
- Current bid/ask
- Spread
- Tick volume
- Market timestamps
- Timezone normalization
- Data freshness checks
- Reconnection handling

Rules:

- Use UTC internally and display timestamps in configurable user timezones.
- Never store account passwords in source code or expose credentials through logs.

### C. Market structure engine

Implement configurable deterministic algorithms for:

1. Swing highs and swing lows
2. HH, HL, LH and LL
3. Bullish and bearish BOS
4. Bullish and bearish CHOCH
5. Market structure shift (MSS)
6. Buy-side liquidity
7. Sell-side liquidity
8. Liquidity sweeps
9. Equal highs and equal lows
10. Displacement candles
11. Fair Value Gap creation
12. FVG mitigation and invalidation
13. Order blocks
14. Premium and discount zones
15. Support and resistance
16. Support/resistance flips
17. Rejection candles
18. Engulfing patterns
19. Multi-timeframe alignment

Rules:

- Each detector must have documented definitions, configurable parameters, unit tests and
  reproducible outputs.
- Do not treat subjective ICT/SMC interpretations as universally established rules.
- Avoid look-ahead bias. Confirmed swing detection must respect the number of future candles
  required for confirmation.

### D. Primary trading model

Initial bullish sequence:

1. M15 bullish directional bias.
2. Identify relevant sell-side liquidity.
3. Confirm a sell-side liquidity sweep.
4. Detect bullish displacement.
5. Confirm bullish MSS.
6. Identify a valid bullish FVG.
7. Wait for price to retrace into the FVG.
8. Confirm M1 bullish entry conditions.
9. Determine invalidation and potential targets.
10. Evaluate risk/reward and trading costs.

Initial bearish sequence uses the corresponding inverse conditions.

Rules:

- Never issue a BUY or SELL recommendation solely because one indicator or pattern appears.
- The system must support `BUY SCENARIO`, `SELL SCENARIO` and `WAIT` decisions.

### E. AI reasoning

Use LangGraph to coordinate:

- Screenshot inspection
- Market-data retrieval
- Market-data validation
- Structure detection
- Multi-timeframe analysis
- Evidence reconciliation
- Trading scenario generation
- Risk assessment
- Structured response validation
- Analysis persistence

Rules:

- The LLM should explain deterministic findings rather than invent market facts.
- Treat screenshot content, external text and model outputs as untrusted inputs.

### F. Probability engine

Build a statistical evaluation module. It must:

- Define precise prediction outcomes.
- Calculate historical setup performance.
- Use chronological train/validation/test splits.
- Support walk-forward testing.
- Avoid data leakage.
- Account for spread, commissions and slippage.
- Calculate win rate, expectancy, drawdown and profit factor.
- Evaluate probability calibration.
- Track sample sizes and confidence intervals.
- Detect data drift.

Rules:

- Never present a rule-based confluence score as a calibrated probability.
- If there is insufficient historical evidence, return a **null probability** and explain why.

### G. Risk management

Implement:

- Configurable risk per trade
- Stop-loss placement
- Take-profit planning
- Risk/reward calculation
- Position-sizing calculator
- Maximum spread threshold
- Minimum reward/risk requirement
- Market-data freshness checks
- Volatility filters
- Session filters
- Optional economic-event restrictions
- Daily and weekly risk limits for future execution support

Default to analysis-only. Do not place live trades.

### H. Trading journal

Record:

- Uploaded screenshot
- Market-data snapshot
- Symbol and timeframe
- Detected structures
- Analysis timestamp
- Model version
- Strategy version
- Suggested scenario
- Entry and invalidation levels
- Estimated probability, when available
- Outcome evaluation
- User notes

Support historical review and performance reports.

### I. User dashboard

Professional responsive interface containing:

- Overview dashboard
- Screenshot upload
- AI analysis workspace
- Live MT5 connection status
- Multi-timeframe bias
- Interactive candlestick chart
- Detected market structures
- Bullish and bearish scenarios
- Entry, SL and TP planning
- Risk/reward display
- Confidence and probability explanations
- Analysis history
- Trading journal
- Backtesting results
- Performance analytics
- AI mentor chat
- Settings

Design rules:

- Professional dark trading interface, readable typography, clear chart overlays, responsive layouts.
- Do not overload the interface with unnecessary indicators or decorative elements.

## 4. Architecture and quality requirements

- Modular Django apps, typed Python where practical, service-layer separation, documented APIs.
- Background jobs for expensive analysis and model evaluation.
- MT5 connectivity optional for development through a clearly labeled mock-data adapter.
- **Never silently substitute mock data for live data.**
- Database migrations, input validation, authentication, authorization, rate limiting, upload size
  limits, secure file handling.
- Unit, integration and end-to-end tests.
- Error handling, logging and operational documentation.

## 5. Mandatory phased-development rules

**THIS PROJECT MUST BE BUILT PHASE BY PHASE.**

- Never attempt to implement the entire platform in one coding session.
- At the beginning of every phase:
  1. Read the master project specification.
  2. Read the current development progress file.
  3. Inspect the repository and existing code.
  4. Identify completed and incomplete requirements.
  5. Produce a phase implementation plan.
  6. Implement only the approved phase scope.
  7. Run relevant tests.
  8. Fix errors introduced by the phase.
  9. Update documentation.
  10. Produce a phase completion report.
- Do not proceed automatically to the next phase. **Wait for explicit approval.**
- Do not claim a feature is complete unless implementation and appropriate verification exist.
- Do not delete or rewrite working code unnecessarily.
- Preserve established architecture unless a change is justified and documented.

## 6. Required project tracking files

- `docs/MASTER_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/PROJECT_PROGRESS.md`
- `docs/DECISIONS.md`
- `docs/TESTING.md`
- `docs/API.md`
- `docs/PHASE_REPORTS/`
- `AGENTS.md`
- `.env.example`

`PROJECT_PROGRESS.md` must contain: current phase, completed phases, completed features,
incomplete features, known issues, test status, next phase, blockers, relevant commit references.

`AGENTS.md` must instruct future coding agents to read the project documentation and respect phase
boundaries before modifying the repository.

At the end of each phase, create a detailed completion report in `docs/PHASE_REPORTS/`.

## 7. Development safety rules

- Never expose API keys.
- Never commit credentials.
- Never enable live trading without separate explicit authorization.
- Never invent market data.
- Never claim guaranteed profitability.
- Never fabricate model accuracy.
- Never silently skip failing tests.
- Never mark untested functionality as verified.
- Never use future market data to generate historical predictions.
- Never let LLM-generated text directly execute trading commands.
- Never overwrite user data without approval.

## 8. Product objective

The objective is **NOT** to guarantee profitable trades or predict markets with certainty. The
objective is to identify potentially high-quality setups, explain the supporting evidence,
calculate trading risk, estimate statistically validated probabilities when sufficient data exists,
and recognize when the appropriate decision is **WAIT**.
