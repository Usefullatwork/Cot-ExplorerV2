# Cot-ExplorerV2

## Overview
Modular trading signal platform: COT + SMC + 19-point confluence scoring.
Python 3.11+, FastAPI, SQLAlchemy/SQLite, Pydantic v2, Vite + vanilla JS frontend.

## Module Map

| Module | Files | Lines | Purpose |
|--------|-------|-------|---------|
| `src/analysis/` | 13 | 2,200+ | Scoring (19pt), SMC, levels, sentiment, setup builder, COT analyzer, technical, geo_classifier, geo_signals, impact_mapper, regime_detector, correlation, signal_tracker |
| `src/api/` | 14 | 1,100+ | FastAPI app, 10 route files, 3 middleware (auth, cache, rate_limit) |
| `src/agents/` | 1+36 | 145+ | Agent registry + 36 YAML prompts across 8 categories |
| `src/competitor/` | 3 | 309 | Competitor analyzer + scrapers (MyFxBook, TradingView) |
| `src/core/` | 3 | 223 | Domain models, enums, error types |
| `src/data/` | 5 | 899 | Price router, rate limiter, providers (CFTC, Stooq, Yahoo, base) |
| `src/db/` | 3 | 815 | SQLAlchemy engine, ORM models, repository (CRUD) |
| `src/pipeline/` | 1 | 158 | Full analysis pipeline runner |
| `src/pine/` | 12 | -- | Pine Script v6 indicators (7), strategies (2), combos (3) |
| `src/publishers/` | 3 | 211 | Telegram, Discord, JSON file signal publishers |
| `src/security/` | 2 | 62 | Input validator, audit log |
| `src/trading/core/` | 11 | 2,640 | Fetch scripts, SMC engine, signal push, build scripts |
| `src/trading/scrapers/` | 11 | -- | Yahoo, Stooq, Twelvedata, Finnhub, FRED, Alpha Vantage, CNN, seismic (USGS), comex (CME), intel_feed (Google News), chokepoints |
| `src/trading/backtesting/` | 9 | 1,998 | Engine, metrics, reports, data loader, models, 4 strategies |
| **Total src/** | **83** | **13,000+** | |
| `tests/unit/` | 28 | 8,700+ | 1,002 test functions |
| `tests/integration/` | 14 | 2,768 | API, DB, pipeline, backtest, provider, signal, competitor tests |
| `frontend/src/` | 25 | 4,100+ | 15 components (5 new), 4 charts, SPA router, state, API client, live ticker |
| `frontend/src/__tests__/` | 10 | 1,500+ | 158 Vitest test cases |

## Commands

### Python
```bash
pytest                                  # Run all 1,002+ tests
pytest tests/unit/                      # Unit tests only
pytest tests/integration/               # Integration tests only
pytest --cov=src --cov-report=term      # Coverage report
ruff check src/ tests/                  # Lint
mypy src/                               # Type check
alembic upgrade head                    # Run DB migrations
alembic revision --autogenerate -m "x"  # Create new migration
python scripts/migrate_v1_data.py       # Migrate v1 data
python scripts/validate_pine.py         # Validate Pine Scripts
```

### Frontend
```bash
cd frontend && npm test                 # Run 158 Vitest tests
cd frontend && npm run dev              # Dev server (port 5173)
cd frontend && npm run build            # Production build -> dist/
```

### Server
```bash
uvicorn src.api.app:app --reload --port 8000   # API dev server
```

### CLI Pipeline (thin wrappers at project root)
```bash
python fetch_cot.py                     # Fetch CFTC COT data
python fetch_all.py                     # Full analysis pipeline
python fetch_prices.py                  # Fetch live prices
python fetch_fundamentals.py            # Fetch FRED macro data
python fetch_calendar.py                # Fetch economic calendar
python push_signals.py                  # Push signals to Telegram/Discord
python smc.py                           # Run SMC analysis
```

## API Routes

10 route groups registered in `src/api/app.py`:
- `health` -- `/health` (GET)
- `signals` -- `/api/signals` (GET)
- `instruments` -- `/api/instruments` (GET)
- `cot` -- `/api/cot` (GET)
- `macro` -- `/api/macro` (GET)
- `webhook` -- `/api/webhook` (POST: push-alert, tv-alert)
- `backtests` -- `/api/backtests` (GET, POST)
- `trading` -- `/api/v1/trading/*` (GET, POST: bot control, positions, signals, config, kill switch)
- `geointel` -- `/api/v1/geointel/*` (GET: seismic, comex, intel, chokepoints, regime, signals, events)
- `correlations` -- `/api/v1/correlations` (GET)
- `signal-log` -- `/api/v1/signal-log` (GET, POST)

Middleware stack: CORS -> RateLimitMiddleware -> APIKeyMiddleware

## Architecture Decisions (Sprint 3)

1. **Thin wrappers** -- 11 root-level scripts delegate to `src/trading/core/` and scrapers for backward compat. Each is <20 lines.
2. **Extracted analysis modules** -- `fetch_all.py` (was 800+ lines) now delegates to `src/analysis/` (scoring, levels, sentiment, setup_builder, technical, smc, cot_analyzer).
3. **Backtesting extracted** -- Engine split from 761 -> 278 lines. Metrics, reports, data_loader, models, and 4 strategy files pulled out.
4. **Provider pattern** -- `src/data/providers/base.py` defines abstract base; CFTC, Stooq, Yahoo implement it. `price_router.py` handles failover.
5. **Security at boundaries** -- `APIKeyMiddleware` + `RateLimitMiddleware` + `InputValidator` protect all API routes. `audit_log.py` for sensitive ops.
6. **SQLAlchemy + Alembic** -- Single SQLite DB via `src/db/engine.py`. All CRUD through `src/db/repository.py`. Migrations in `alembic/versions/`.
7. **Type hints everywhere** -- Full type annotations added across all `src/` modules. Validated with mypy.
8. **Agent prompt system** -- 36 YAML prompts in `src/agents/prompts/` (8 categories), loaded by `src/agents/registry.py`.

## Data Sources (all legal, free tier)
- CFTC.gov (public domain)
- FRED (public domain)
- Yahoo Finance (personal use)
- Stooq (free, no key)
- Twelvedata (800/day free)
- Finnhub (60/min free)
- Alpha Vantage (25/day free)
- USGS Earthquake Feed (public domain, no key)
- CME COMEX Warehouse Reports (public, no key)
- Google News RSS (public, no key, rate-limited 2s between categories)

## Security
- API key auth: `SCALP_API_KEY` env var, constant-time comparison (hmac.compare_digest)
- TradingView webhook: `TV_WEBHOOK_SECRET` env var for payload verification
- Rate limiting: per-IP sliding window (60/min default), 10K IP memory cap
- XSS: escapeHtml() on all frontend API data rendering
- CI: SHA-pinned third-party GitHub Actions (codecov, trufflehog)
- CSO audit report: `.gstack/security-reports/`

## Trading Bot (19 instruments)
- 17 instruments in SYMBOL_MAP (forex, commodities, indices)
- 6 crisis instruments: NATGAS, WHEAT, CORN, XPTUSD, XPDUSD, USDCHF
- 6 market regimes: NORMAL, RISK_OFF, CRISIS, WAR_FOOTING, ENERGY_SHOCK, SANCTIONS
- 12 entry filters + 8 exit rules (geo_spike, ATR trailing, triple TP, session exit)
- Broker: Pepperstone cTrader (placeholder endpoints, not production-ready)

## Rules
- Real data only -- no synthetic/placeholder data
- All agents must validate against YAML schema
- Type hints required on all public functions
- Tests required for new modules (pytest for Python, Vitest for JS)
- Thin wrappers at root must stay <20 lines
- Never commit .env or API keys
