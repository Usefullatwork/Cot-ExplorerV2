# Cot-ExplorerV2 — Deep Review & Improvement Session

> **Use this prompt in a fresh Claude Code session with [gstack](https://github.com/garrytan/gstack) installed.**
> Run: `/office-hours` first, then follow the sprint flow below.

---

## Project Context

You are working on **Cot-ExplorerV2** — a full-stack trading signal generation and automated execution platform.

**Repo**: https://github.com/Usefullatwork/Cot-ExplorerV2
**Local path**: `C:\Users\MadsF\Desktop\Cot-ExplorerV2`
**Stack**: Python 3.13, FastAPI, SQLAlchemy/SQLite (14 tables), Pydantic v2, Pine Script v6, Vite + vanilla JS
**Python**: `C:\Users\MadsF\AppData\Local\Programs\Python\Python313\python.exe`
**Tests**: `python -m pytest tests/ -v --tb=short` (800+ tests)
**Frontend tests**: `cd frontend && npm test`
**Lint**: `ruff check src/ tests/`

---

## What This System Does

### Signal Generation Pipeline
1. **CFTC COT data** — Downloads 4 report types weekly (TFF, Legacy, Disaggregated, Supplemental). Tracks speculator/commercial/non-reportable positioning, net position percentiles, momentum classification (ØKER/SNUR/STABIL).
2. **Price data** — 5 providers with auto-failover: TradingView WebSocket → Twelvedata → Stooq → Yahoo → Finnhub. Daily + intraday (15m, 1H, 4H).
3. **Smart Money Concepts (SMC)** — 3-timeframe analysis (15m/1H/4H): supply/demand zones, break of structure (BOS), swing classification (HH/LH/HL/LL), **Fair Value Gaps**, **Order Blocks**, **Liquidity Sweeps**, zone recency weighting, zone touch counting.
4. **Fundamental scoring** — FRED macro data (GDP, CPI, NFP, Claims, JOLTS, retail sales). Weighted categories: growth 25%, inflation 40%, jobs 35%. Per-instrument USD directional bias.
5. **Sentiment** — CNN Fear & Greed Index, Google News + BBC RSS risk-on/risk-off scoring, macro indicators (HYG, TIP, TNX, IRX, Copper, EEM).
6. **16-point confluence scoring** — Combines all factors into A+/A/B/C grade. Thresholds: A+ ≥14, A ≥12, B ≥8, C <8.
7. **Level-to-Level (L2L) setups** — Entry at structural levels, structural stop loss, T1/T2/T3 targets with R:R calculation.
8. **Dollar Smile Model** — USD regime classification (risk-off / goldilocks / growth) using VIX, DXY momentum, HY credit stress.

### Trade Execution
1. **TradingView Pine Script v6 alerts** → webhook POST to FastAPI (`/api/v1/webhook/tv-alert`)
2. **Entry confirmation** — Zone proximity, 5m candle confirmation, EMA9 filter, **session filter** (London/NY), **news blackout** (60min before high-impact events), **spread monitoring**, **correlation limiter**, **RSI counter-trend filter**
3. **Broker execution** — Abstract `BrokerAdapter` with Pepperstone EU (CySEC, ESMA-compliant) + paper trading adapters
4. **Position management** — 8 exit rules: T1/T2/T3 partial close, ATR trailing stop, breakeven+buffer, EMA9 cross exit, 8/16-candle time rules, geo-spike emergency close, session-based exit
5. **Lot sizing** — VIX regime × grade tier matrix with drawdown-adjusted sizing, anti-martingale, spread buffer deduction
6. **Risk controls** — Equity curve circuit breaker (10% DD pause), daily loss limit (3), consecutive loss scaling, weekly cap (-5%), VIX halt (>40), kill switch

### Backtesting & Optimization
1. **4 strategies** — COT momentum, SMC confluence, mean reversion, macro regime
2. **Walk-forward optimizer** — 4 strategies × 5 timeframes × 640 parameter combinations, rolling train/test windows
3. **Backtest realism** — 1 pip slippage, 0.2 pip commission, spread modeling per instrument
4. **Monte Carlo simulation** — 5000-iteration trade reshuffle, confidence intervals, probability of ruin, max drawdown distribution
5. **Stability analysis** — Flags single-window winners (overfitting risk)

### Infrastructure
- **FastAPI** — 20+ endpoints, 9 route groups, API key auth, rate limiting, CORS, audit logging
- **14 SQLite tables** — Instruments, prices (daily + intraday), COT positions, signals, backtests, fundamentals, calendar events, audit log, bot config, bot signals, bot positions, bot trade log
- **Signal dispatch** — Telegram bot, Discord webhook, JSON file export
- **15 Pine Script v6 files** — 10 indicators, 2 strategies, 3 combos. 9 webhook alert conditions.
- **Vite + vanilla JS frontend** — 8 tabs: Setups, Macro, COT, Calendar, Backtest, Pine, Competitor, Trading
- **Deployment** — Docker multi-stage, Raspberry Pi systemd, cron scheduler (4x daily)

---

## Current Architecture (Key Files)

```
src/
├── analysis/           # Scoring, SMC, levels, sentiment, setup builder, COT analyzer
│   ├── scoring.py      # 16-point confluence scoring (A+/A/B/C grades)
│   ├── smc.py          # SMC engine + FVGs + Order Blocks + Liquidity Sweeps
│   ├── levels.py       # Support/resistance detection (PDH/PDL/PWH/PWL)
│   ├── sentiment.py    # News sentiment, Fear & Greed, macro indicators
│   └── setup_builder.py # L2L trade setup generation
├── api/                # FastAPI app, 8 route files, 3 middleware
│   ├── routes/trading.py   # 10 bot endpoints + TV webhook
│   └── routes/signals.py   # Signal listing/filtering
├── core/               # Domain models, enums (16 enums), errors
├── data/               # Price router, rate limiter, 5 providers
│   └── providers/tradingview.py  # TradingView WebSocket (highest priority)
├── db/                 # SQLAlchemy engine, 14 ORM models, repository (CRUD)
├── pine/               # 15 Pine Script v6 files (indicators, strategies, combos)
├── publishers/         # Telegram, Discord, JSON signal dispatch
├── trading/
│   ├── bot/            # Entry logic, position mgr, lot sizing, kill switch, risk manager
│   │   ├── broker/     # Abstract adapter, paper.py, pepperstone.py
│   │   ├── entry_logic.py      # 11-step entry evaluation
│   │   ├── position_manager.py # 8 exit rules
│   │   ├── lot_sizing.py       # VIX×grade matrix + drawdown adjustment
│   │   ├── risk_manager.py     # Equity curve, daily limits, VIX halt
│   │   └── kill_switch.py      # Emergency close-all
│   ├── backtesting/    # Engine, 4 strategies, optimizer, Monte Carlo, reports
│   │   ├── engine.py           # Backtest with slippage/commission/spread
│   │   ├── optimizer.py        # Walk-forward 640-combo grid search
│   │   └── monte_carlo.py      # 5000-iteration trade reshuffle
│   ├── core/           # Fetch scripts (COT, prices, fundamentals, calendar)
│   └── scrapers/       # 7 data source scrapers
├── security/           # Input validation, audit logging
frontend/
├── src/components/     # 10 components (SetupGrid, MacroPanel, BotPanel, etc.)
├── src/charts/         # 4 chart types (price, COT bar, radar, P&L curve)
tests/
├── unit/               # 24+ test files
└── integration/        # 15+ test files
```

---

## 12 Instruments Tracked

EURUSD, USDJPY, GBPUSD, AUDUSD (forex), Gold, Silver, Brent, WTI (commodities), SPX, NAS100, DXY, VIX (indices/vol)

---

## What Needs Deep Review

### 1. Code Quality & Architecture (`/review`, `/plan-eng-review`)
- Are the analysis modules (scoring, SMC, levels) well-separated or leaking concerns?
- Is the bot module (entry → position → risk) properly layered?
- Are there dead code paths, unused imports, or redundant logic?
- Are the 14 DB models properly normalized?
- Is the repository pattern (CRUD) consistent across all 14 tables?
- Are there any circular imports or import-time side effects?

### 2. Trading Logic Correctness (`/investigate`)
- **Scoring**: Do the 16 criteria produce sensible grades? Are thresholds calibrated?
- **SMC**: Are FVG/OB/liquidity sweep detections algorithmically correct? Edge cases?
- **Entry logic**: Does the 11-step evaluation chain have the right priority order?
- **Position management**: Do the 8 exit rules interact correctly? Can they conflict?
- **Lot sizing**: Does the VIX×grade matrix + drawdown adjustment + anti-martingale stack correctly?
- **Risk manager**: Does the equity curve circuit breaker actually prevent catastrophic drawdowns?
- **Monte Carlo**: Is the reshuffle methodology statistically valid?

### 3. Security (`/cso`)
- API key auth — is it properly enforced on all endpoints?
- Input validation — are all user-facing inputs sanitized?
- SQL injection — SQLAlchemy parameterization OK?
- Rate limiting — is it per-IP, per-key, or global?
- Audit logging — are all state-changing operations logged?
- Secrets — is .env properly gitignored? Any hardcoded keys?
- Broker credentials — how are they stored and accessed?

### 4. Testing Gaps (`/qa`)
- 800+ tests exist but are there untested modules?
- Are the Monte Carlo tests statistically meaningful?
- Are the SMC FVG/OB tests covering all edge cases?
- Is the backtesting engine tested with realistic slippage?
- Frontend: only ~88 Vitest tests — is the new BotPanel tested?
- Integration tests: do they cover the full signal→bot→broker flow?

### 5. Performance (`/benchmark`)
- Is the walk-forward optimizer efficient? (4×5×640 = 12,800 backtests)
- Is the Monte Carlo simulation fast enough? (5000 iterations)
- Is the price router's failover chain adding latency?
- Frontend: are there unnecessary re-renders or memory leaks?
- Database: are the 30+ indexes actually being used by queries?

### 6. Design & UX (`/plan-design-review`, `/design-consultation`)
- Frontend has 8 tabs — is the information architecture intuitive?
- BotPanel: are the 7 sections (status, positions, signals, P&L, kill-switch, config, log) well-organized?
- Are trading signals presented clearly enough for quick decision-making?
- Is the kill-switch UX safe (confirmation dialog, undo)?
- Mobile responsiveness?

### 7. Pine Script Quality
- Are the 15 Pine v6 files following best practices?
- Do the 9 alert conditions produce clean JSON payloads?
- Are the FVG/OB indicators performant on TradingView (no repainting)?
- Do the combo scripts (overlay, score, macro) fit within TradingView's 3-indicator limit?

---

## Suggested gstack Sprint Flow

```
1. /office-hours          → Rethink: is the signal→execution pipeline optimal?
2. /plan-ceo-review       → Scope: what should V3 focus on?
3. /plan-eng-review       → Architecture: are the modules well-separated?
4. /plan-design-review    → UX: is the 8-tab frontend coherent?
5. /review                → Code quality: find production bugs
6. /cso                   → Security audit: OWASP Top 10 + trading-specific risks
7. /qa                    → Test the frontend in real browser, find visual bugs
8. /benchmark             → Performance baseline: API latency, optimizer speed
9. /investigate           → Debug any issues found in review/qa
10. /ship                 → Run tests, open PR with fixes
11. /retro                → What did we learn? Update CLAUDE.md
```

---

## Key Commands

```bash
# Backend
cd C:\Users\MadsF\Desktop\Cot-ExplorerV2
python -m pytest tests/ -v --tb=short           # Run all tests
python -m pytest tests/unit/ -v                  # Unit tests only
ruff check src/ tests/                           # Lint
python -m uvicorn src.api.app:app --reload       # Start API (port 8000)

# Frontend
cd frontend && npm test                          # Vitest (88 tests)
cd frontend && npm run dev                       # Vite dev server (port 5173)

# Pipeline
python fetch_all.py                              # Full analysis pipeline
python push_signals.py                           # Push to Telegram/Discord

# Optimizer
python -m src.trading.backtesting.optimizer --instrument EURUSD

# Monte Carlo
python -c "from src.trading.backtesting.monte_carlo import run_monte_carlo, print_summary; trades = [150]*6 + [-100]*4; print(print_summary(run_monte_carlo(trades*10, iterations=5000)))"

# Pine validation
python scripts/validate_pine.py
```

---

## Recent Commits (Context)

```
cedb405 feat: overnight sprint — advanced SMC, risk controls, Monte Carlo, 16-point scoring
62ffce9 docs: rewrite README with trading bot, optimizer, Pine v6, broker integration
c88ec97 feat: add trading bot, TradingView webhooks, walk-forward optimizer, Pine Script v6
fdad070 fix: resolve UTF-8 double-encoding through Vite proxy for Norwegian characters
cb2921a feat: overhaul MacroPanel with big charts, sentiment card, expanded data
```

---

## Ground Rules

- **Python path**: `C:\Users\MadsF\AppData\Local\Programs\Python\Python313\python.exe`
- **Git commits**: Use `-m` flag (HEREDOC hangs on Windows)
- **Git staging**: Stage files by name (never `git add .` — timeouts on large repos)
- **Node**: Don't run npm on D: drive (HDD — causes timeouts)
- **Tests**: Run `python -m pytest` not `npx jest` (ESM loader issues)
- **Broker**: Pepperstone EU (CySEC) — ESMA-compliant, 30:1 leverage max
- **All agents must use `bypassPermissions` mode**
