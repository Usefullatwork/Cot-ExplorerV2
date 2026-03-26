# Cot-ExplorerV2

**Trading signal platform with automated execution: COT + SMC + 12-point confluence scoring + TradingView webhooks + broker integration**

A full-stack trading intelligence and execution platform combining CFTC Commitments of Traders analysis, Smart Money Concepts (SMC) technical analysis, fundamental macro scoring, backtesting with walk-forward optimization, and automated trade execution via TradingView webhooks and broker REST APIs.

Built on Python 3.13, FastAPI, SQLAlchemy, Pydantic v2, Pine Script v6, and Vite + vanilla JS.

## Features

### Signal Generation
- **12-Point Confluence Scoring** -- SMA200, momentum, COT, fundamentals, SMC structure, news sentiment, event risk
- **COT Analysis** -- 4 CFTC report types (TFF, Legacy, Disaggregated, Supplemental) with positioning, percentiles, momentum
- **SMC Engine** -- Supply/demand zones, break of structure (BOS), swing classification (HH/LH/HL/LL), 3 timeframes (15m/1H/4H)
- **Fundamental Scoring** -- FRED macro data: GDP, CPI, NFP, Claims, JOLTS. Weighted categories: growth (25%), inflation (40%), jobs (35%)
- **Dollar Smile Model** -- USD regime classification with VIX, HY spreads, yield curve, conflict detection

### Trade Execution
- **TradingView Webhooks** -- Pine Script v6 alerts POST JSON to FastAPI webhook endpoints
- **Broker Integration** -- Abstract `BrokerAdapter` interface with Pepperstone EU (CySEC) and paper trading adapters
- **Entry Confirmation** -- Zone proximity, 5m candle confirmation, EMA9 filter
- **Position Management** -- T1 partial close (50%), EMA9 trailing exit, 8/16-candle time rules, geo-spike emergency close
- **Kill Switch** -- Emergency close-all via API endpoint or frontend button
- **Lot Sizing** -- VIX regime x grade tier matrix (full/half/quarter/blocked)

### Backtesting & Optimization
- **4 Strategies** -- COT momentum, SMC confluence, mean reversion, macro regime
- **Walk-Forward Optimizer** -- Rolling train/test windows, parameter grid search (640 combinations), overfitting detection
- **Multi-Timeframe** -- Test across 5m, 15m, 1H, 4H, D1
- **Metrics** -- Sharpe ratio, win rate, max drawdown, profit factor, composite scoring

### Infrastructure
- **FastAPI Backend** -- 20+ endpoints across 9 route groups, API key auth, rate limiting, audit logging
- **14 SQLite Tables** -- Instruments, prices, COT, signals, backtests, fundamentals, calendar, bot state
- **5 Data Providers** -- TradingView (WebSocket), Twelvedata, Stooq, Yahoo, Finnhub with automatic failover
- **Signal Dispatch** -- Telegram bot, Discord webhook, JSON file export
- **Pine Script v6** -- 12 TradingView indicators/strategies with 9 webhook alert conditions
- **782 Tests** -- Unit + integration (Python) + frontend (Vitest)

## Architecture

```
TradingView (Pine Script v6 alerts)
        |
        v  HTTPS webhook
+-------+--------------------------------------------------+
|  COT EXPLORER V2 (FastAPI)                                |
|                                                            |
|  Data Layer        Analysis Layer      API Layer           |
|  - 5 providers     - 12-pt scoring     - /signals          |
|  - COT fetcher     - SMC engine        - /cot, /macro      |
|  - FRED macro      - sentiment         - /trading (10 ep)  |
|  - calendar        - levels            - /webhook/tv-alert |
|                                                            |
|  Trading Bot (src/trading/bot/)                            |
|  - entry_logic     - position_mgr      - lot_sizing        |
|  - kill_switch     - broker adapters   - bot_manager       |
|                                                            |
|  Backtesting (src/trading/backtesting/)                    |
|  - 4 strategies    - walk-forward      - param grid        |
|  - metrics         - reports           - optimizer         |
|                                                            |
|  Frontend (Vite + vanilla JS, 8 tabs)                      |
|  - Setups  - Macro  - COT  - Calendar                     |
|  - Backtest  - Pine  - Competitor  - Trading               |
+-------+--------------------------------------------------+
        |
        v  REST API (HTTP)
   Broker (Pepperstone EU / Paper Trading)
```

## Quick Start

### Prerequisites

- Python 3.11+ (3.13 recommended)
- Node.js 18+ (frontend)

### Install

```bash
git clone https://github.com/Usefullatwork/Cot-ExplorerV2.git
cd Cot-ExplorerV2

# Backend
pip install -e ".[dev]"
alembic upgrade head

# Frontend
cd frontend && npm install && cd ..
```

### Run

```bash
# Terminal 1: API server
uvicorn src.api.app:app --reload --port 8000

# Terminal 2: Frontend dev server
cd frontend && npm run dev
```

Open http://localhost:5173 -- the dashboard proxies API calls to port 8000.

### Run the Analysis Pipeline

```bash
python fetch_cot.py              # Fetch CFTC COT data
python fetch_all.py              # Full analysis (prices, SMC, scoring, setups)
python push_signals.py           # Push signals to Telegram/Discord
```

## API Endpoints

All endpoints accept optional `X-API-Key` header (set via `SCALP_API_KEY` env var).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System status, uptime, DB metrics |
| `GET` | `/api/v1/signals` | Scored trade setups (filter by grade, timeframe) |
| `GET` | `/api/v1/instruments` | 12 tracked instruments |
| `GET` | `/api/v1/cot` | COT positioning + history |
| `GET` | `/api/v1/macro` | Dollar Smile, VIX regime, macro indicators |
| `POST` | `/api/v1/webhook/push-alert` | Signal ingestion (pipeline) |
| `POST` | `/api/v1/webhook/tv-alert` | TradingView alert ingestion |
| `GET` | `/api/v1/backtests/summary` | Backtest aggregate stats |
| `GET` | `/api/v1/trading/status` | Bot status, broker connection |
| `GET` | `/api/v1/trading/positions` | Active positions + P&L |
| `GET` | `/api/v1/trading/signals` | Signal queue |
| `POST` | `/api/v1/trading/invalidate` | Kill switch (close all) |
| `GET/POST` | `/api/v1/trading/config` | Bot configuration |
| `POST` | `/api/v1/trading/start` | Start bot |
| `POST` | `/api/v1/trading/stop` | Stop bot |

## Instruments

| Key | Category | COT Market | Session |
|-----|----------|------------|---------|
| EURUSD | Forex | Euro FX | London 08-12 CET |
| USDJPY | Forex | Japanese Yen | London 08-12 CET |
| GBPUSD | Forex | British Pound | London 08-12 CET |
| AUDUSD | Forex | Australian Dollar | London 08-12 CET |
| Gold | Commodity | Gold | London/NY Fix |
| Silver | Commodity | Silver | London/NY Fix |
| Brent | Commodity | Crude Oil | London/NY Fix |
| WTI | Commodity | Crude Oil | London/NY Fix |
| SPX | Index | S&P 500 | NY Open 14:30-17:00 CET |
| NAS100 | Index | Nasdaq Mini | NY Open 14:30-17:00 CET |
| DXY | Index | USD Index | London 08-12 CET |
| VIX | Volatility | -- | NY Open (position sizing only) |

## Scoring System

Each instrument scores 0-12 on confluence criteria:

1. Above SMA200 (D1 trend)
2. 20-day momentum confirms
3. COT confirms direction
4. COT strong (>10% of OI)
5. Price AT HTF level now
6. HTF level nearby (D1/Weekly)
7. D1 + 4H trend aligned
8. No event risk within 4 hours
9. News sentiment confirms
10. Fundamentals confirm
11. BOS 1H/4H confirms
12. SMC 1H structure confirms

**Grades:** A+ (11+) | A (9+) | B (6+) | C (<6)

## Trading Bot

The bot receives signals via TradingView webhooks or the analysis pipeline and executes trades through a broker REST API.

### Entry Logic
1. Signal received (instrument, direction, grade, score, entry/SL/T1/T2)
2. Zone proximity check (price within ATR tolerance of entry level)
3. 5m candle confirmation (closes in direction within 6 candles)
4. EMA9 filter (15m EMA9 supports direction)
5. Market order sent to broker

### Position Management
| Rule | Trigger | Action |
|------|---------|--------|
| T1 | Price hits target 1 | Close 50%, move SL to breakeven |
| EMA9 Cross | EMA9 crosses against (after T1) | Close remaining |
| 8-Candle | 8 x 5m candles without T1 | Close 50% |
| 16-Candle | 16 x 5m candles (after partial) | Close remaining |
| Geo-Spike | >2x ATR against position | Emergency close all |
| Kill Switch | Manual or API trigger | Close everything |

### Lot Sizing (VIX x Grade)

| VIX / Grade | A+ | A | B | C |
|-------------|-----|---|---|---|
| Normal (<20) | 1.0x | 1.0x | 0.6x | 0.3x |
| Elevated (20-30) | 0.6x | 0.6x | 0.3x | 0.3x |
| Extreme (>30) | 0.3x | 0.3x | 0.3x | 0.0x |

## Walk-Forward Optimizer

Automated strategy optimization with overfitting detection:

```bash
python -m src.trading.backtesting.optimizer --instrument EURUSD
```

- Tests 4 strategies x 5 timeframes x 640 parameter combinations
- Walk-forward: train on 6 months, validate on 2 months, slide forward
- Composite scoring: 0.3*Sharpe + 0.25*WinRate + 0.25*(1-MaxDD) + 0.2*ProfitFactor
- Stability analysis flags single-window winners (overfitting risk)

## Pine Script v6

12 TradingView indicators with webhook alerts:

| File | Category | Alert Conditions |
|------|----------|-----------------|
| `cot_explorer_score.pine` | Combo | Grade A/A+ long/short, exit below B |
| `cot_explorer_overlay.pine` | Combo | L2L entry touch, zone touch, VIX change |
| `cot_explorer_macro.pine` | Combo | -- |
| `confluence_score.pine` | Indicator | -- |
| `cot_overlay.pine` | Indicator | -- |
| `smc_zones.pine` | Indicator | -- |
| `l2l_levels.pine` | Indicator | -- |
| `vix_regime.pine` | Indicator | -- |
| `macro_dashboard.pine` | Indicator | -- |
| `dollar_smile.pine` | Indicator | -- |
| `cot_reversal.pine` | Strategy | -- |
| `smc_confluence.pine` | Strategy | -- |

## Data Sources

| Source | Data | Key Required |
|--------|------|--------------|
| TradingView | Real-time quotes (WebSocket) | No |
| CFTC.gov | COT reports (4 types) | No |
| Stooq | Daily OHLC | No |
| Yahoo Finance | OHLC, intraday | No |
| FRED | Macro series (GDP, CPI, NFP) | Yes (free) |
| Twelvedata | Forex/commodity OHLC | Yes (free) |
| Finnhub | Real-time quotes | Yes (free) |
| CNN | Fear & Greed Index | No |

## Environment Variables

```bash
# Data sources (all optional -- system works with public data)
TWELVEDATA_API_KEY=
FINNHUB_API_KEY=
FRED_API_KEY=

# Signal dispatch (optional)
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK=

# API authentication (optional)
SCALP_API_KEY=

# Trading bot broker (optional)
PEPPERSTONE_API_KEY=
PEPPERSTONE_ACCOUNT_ID=
BROKER_MODE=paper              # paper | demo | live

# Server
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
DATABASE_URL=sqlite:///data/cot-explorer.db
```

## Testing

```bash
# Python tests (782 functions)
pytest                                    # All tests
pytest tests/unit/                        # Unit tests only
pytest tests/integration/                 # Integration tests
pytest --cov=src --cov-report=term        # With coverage

# Frontend tests (88 cases)
cd frontend && npm test

# Lint
ruff check src/ tests/
```

## Deployment

### Docker

```bash
docker-compose up                                    # API only
docker-compose --profile with-scheduler up           # API + cron scheduler
```

### Raspberry Pi

```bash
bash scripts/rpi-setup.sh     # Install deps, create venv, enable systemd
```

### Manual (systemd)

```bash
sudo cp scripts/cot-explorer.service /etc/systemd/system/
sudo systemctl enable cot-explorer
sudo systemctl start cot-explorer
```

## Project Stats

| Metric | Value |
|--------|-------|
| Python source files | 123 |
| Python LOC (src/) | 13,933 |
| Database tables | 14 |
| API endpoints | 20+ |
| Test functions | 782 |
| Pine Script files | 12 (v6) |
| Instruments tracked | 12 |
| Backtesting strategies | 4 |
| Data providers | 5 (with failover) |
| Frontend components | 10 |
| Frontend tabs | 8 |

## License

MIT
