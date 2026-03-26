# Cot-ExplorerV2

**Modular trading signal platform: COT + SMC + 12-point confluence scoring**

A modular trading intelligence platform combining CFTC Commitments of Traders analysis, Smart Money Concepts (SMC) technical analysis, fundamental macro scoring, backtesting, and a FastAPI-served dashboard -- built on Python 3.11+ with FastAPI, SQLAlchemy, and Pydantic v2.

## Features

- **COT Analysis** -- Downloads and parses all 4 CFTC report types (TFF, Legacy, Disaggregated, Supplemental) with Norwegian market name mapping and category classification
- **SMC Engine** -- Full Smart Money Concepts implementation: swing structure (HH/LH/HL/LL), supply/demand zones, break of structure (BOS), multi-timeframe analysis (15m/1H/4H)
- **Fundamental Scoring** -- EdgeFinder-style macro scoring with FRED data: GDP, CPI, NFP, Claims, JOLTS + weighted category consensus
- **Multi-Source Pricing** -- Priority waterfall with automatic failover: Twelvedata -> Stooq -> Yahoo Finance, with per-provider rate limiting
- **12-Point Scoring** -- Each instrument scored on SMA200, momentum, COT, fundamentals, SMC structure, news sentiment, event risk
- **Dollar Smile Model** -- Dynamic USD regime classification with VIX, HY spreads, yield curve
- **Backtesting** -- Strategy backtesting engine with 4 built-in strategies (COT momentum, SMC confluence, mean reversion, macro regime), equity curves, and metrics
- **FastAPI Backend** -- 7 route groups with API key auth, per-IP rate limiting, response caching, and input validation
- **Vite + Vanilla JS Frontend** -- Dashboard with Chart.js/Lightweight Charts, 10 components, SPA router
- **Pine Script Library** -- 12 TradingView indicators and strategies (v5)
- **Signal Dispatch** -- Push top setups to Telegram, Discord, and JSON file endpoints
- **Security** -- Input validation, audit logging, API key middleware
- **603 Python tests + 88 frontend tests** -- Unit + integration coverage across all modules

## Architecture

```
Cot-ExplorerV2/
|-- src/
|   |-- analysis/           # Scoring, SMC, levels, sentiment, setup builder (7 files, 1,145 lines)
|   |-- api/                # FastAPI app, routes (7), middleware (auth, cache, rate_limit)
|   |-- agents/             # Agent prompt registry + 36 YAML prompts (8 categories)
|   |-- competitor/         # Competitor scrapers (MyFxBook, TradingView)
|   |-- core/               # Domain models, enums, error types
|   |-- data/               # Price router, rate limiter, providers (CFTC, Stooq, Yahoo)
|   |-- db/                 # SQLAlchemy engine, models, repository (CRUD)
|   |-- pipeline/           # Full analysis pipeline runner
|   |-- pine/               # 12 Pine Script v5 indicators + strategies
|   |-- publishers/         # Telegram, Discord, JSON file publishers
|   |-- security/           # Input validator, audit log
|   |-- trading/
|       |-- core/           # Fetch scripts, SMC engine, signal push (11 files)
|       |-- scrapers/       # 7 data source scrapers (Yahoo, Stooq, Twelvedata, etc.)
|       |-- backtesting/    # Engine, metrics, reports, 4 strategies
|
|-- tests/
|   |-- unit/               # 18 unit test files (603 test functions total)
|   |-- integration/        # 14 integration test files
|   |-- fixtures/           # Shared test data (prices, COT, levels)
|
|-- frontend/               # Vite + vanilla JS dashboard
|   |-- src/
|       |-- components/     # 10 UI components (CotTable, SetupCard, MacroPanel, etc.)
|       |-- charts/         # 4 Chart.js/Lightweight Charts wrappers
|       |-- __tests__/      # 5 Vitest test files (88 test cases)
|       |-- styles/         # 9 CSS modules (1,252 lines)
|
|-- alembic/                # Database migrations (SQLite)
|-- config/                 # instruments.yaml, scoring.yaml
|-- scripts/                # Migration + Pine validation utilities
|-- docs/                   # Architecture, API reference, deployment guides
|
|-- fetch_cot.py            # Thin wrapper -> src/trading/core/fetch_cot.py
|-- fetch_all.py            # Thin wrapper -> src/trading/core/fetch_all.py
|-- fetch_prices.py         # Thin wrapper -> src/trading/core/fetch_prices.py
|-- (+ 5 more thin wrappers for backward compatibility)
```

**Key stats:** 67 Python source files | 10,371 lines in `src/` | 603 Python tests | 88 frontend tests | 12 Pine Scripts

## Installation

### Prerequisites

- Python 3.11+ (3.13 recommended)
- Node.js 18+ (for frontend and security tools)

### Backend

```bash
git clone https://github.com/Usefullatwork/Cot-ExplorerV2.git
cd Cot-ExplorerV2

# Install Python dependencies
pip install -e ".[dev]"

# Initialize the database
alembic upgrade head
```

### Frontend

```bash
cd frontend
npm install
```

### Environment Variables

Create a `.env` file or export directly:

```bash
# Required for API authentication
COT_API_KEY="your-api-key"

# Data source API keys (optional -- enhances data coverage)
FRED_API_KEY="your-key"
TWELVEDATA_API_KEY="your-key"
FINNHUB_API_KEY="your-key"

# Signal dispatch (optional)
TELEGRAM_TOKEN="your-bot-token"
TELEGRAM_CHAT_ID="your-chat-id"
DISCORD_WEBHOOK_URL="your-webhook-url"

# CORS (default: http://localhost:3000)
CORS_ORIGINS="http://localhost:3000,http://localhost:5173"
```

## Quick Start

```bash
# Start the API server
uvicorn src.api.app:app --reload --port 8000

# Start the frontend dev server (separate terminal)
cd frontend && npm run dev

# -- OR run the CLI pipeline directly --

# Fetch COT data (no API key needed)
python fetch_cot.py

# Run full analysis pipeline
python fetch_all.py

# Push signals to Telegram/Discord
python push_signals.py
```

## API Endpoints

All endpoints require the `X-API-Key` header (set via `COT_API_KEY` env var).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check + system status |
| `GET` | `/api/signals` | Current scored trade setups |
| `GET` | `/api/instruments` | Tracked instrument list |
| `GET` | `/api/cot` | Latest COT positioning data |
| `GET` | `/api/macro` | Macro fundamental scores |
| `POST` | `/api/webhook` | Incoming webhook handler |
| `GET` | `/api/backtests` | Backtest results |
| `POST` | `/api/backtests` | Run a new backtest |

Full API reference: [`docs/api-reference.md`](docs/api-reference.md)

## Testing

```bash
# Run all Python tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run frontend tests
cd frontend && npm test
```

## Data Sources

| Source | Data | Rate Limit | Key Required |
|--------|------|------------|--------------|
| CFTC.gov | COT reports (4 types) | Unlimited | No |
| FRED | GDP, CPI, NFP, rates | 120/min | Yes (free) |
| Yahoo Finance | OHLC, quotes | Unofficial | No |
| Stooq | Daily OHLC | Unlimited | No |
| Twelvedata | OHLC, forex | 800/day | Yes (free) |
| Finnhub | Realtime quotes | 60/min | Yes (free) |
| Alpha Vantage | OHLC, forex | 25/day | Yes (free) |
| CNN | Fear & Greed Index | Unofficial | No |
| ForexFactory | Economic calendar | Unofficial | No |

## Scoring System

Each instrument is scored on 12 criteria (0-12 points):

1. Above SMA200 (daily trend)
2. 20-day momentum confirms direction
3. COT confirms direction
4. COT strong positioning (>10% of OI)
5. Price AT HTF level now
6. HTF level nearby (D1/Weekly)
7. D1 + 4H trend aligned
8. No high-impact events within 4 hours
9. News sentiment confirms
10. Fundamentals confirm
11. BOS 1H/4H confirms direction
12. SMC 1H structure confirms

**Grades:** A+ (11+) | A (9+) | B (6+) | C (<6)

**Timeframe classification:**
- MAKRO: Score >= 6 + COT confirms + HTF level (hold days/weeks)
- SWING: Score >= 4 + HTF level (hold hours/days)
- SCALP: Score >= 2 + at level + active session (minutes)
- WATCHLIST: Not ready

## License

MIT
