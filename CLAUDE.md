# Cot-ExplorerV2

## Overview
Modular trading signal platform: COT + SMC + 19-point confluence scoring.
Python 3.11+, FastAPI, SQLAlchemy/SQLite, Pydantic v2, Vite + vanilla JS frontend.

## Module Map

| Module | Files | Lines | Purpose |
|--------|-------|-------|---------|
| `src/analysis/` | 29 | 7,500+ | Scoring (19pt), SMC, levels, sentiment, setup builder, COT analyzer, technical, geo_classifier, geo_signals, impact_mapper, regime_detector, correlation, signal_tracker, adr_calculator, portfolio_risk, stress_test, kelly, signal_monitor, drift_detector, rebalancer, risk_parity, bootstrap, microstructure, nlp_sentiment, signal_propagation, signal_statistics, transaction_costs, attribution |
| `src/api/` | 18 | 2,000+ | FastAPI app, 14 route files (incl. pipeline), 4 middleware, lifespan scheduler |
| `src/agents/` | 1+36 | 145+ | Agent registry + 36 YAML prompts across 8 categories |
| `src/competitor/` | 3 | 309 | Competitor analyzer + scrapers (MyFxBook, TradingView) |
| `src/core/` | 3 | 223 | Domain models, enums, error types |
| `src/data/` | 5 | 899 | Price router, rate limiter, providers (CFTC, Stooq, Yahoo, base) |
| `src/db/` | 3 | 900+ | SQLAlchemy engine, ORM models (21 tables incl. pipeline_state, pipeline_runs), repository (CRUD) |
| `src/pipeline/` | 5 | 1,100+ | Pipeline runner (13 stages), Layer 2 runner, gate orchestrator (8 gates), execution bridge, APScheduler |
| `src/pine/` | 12 | -- | Pine Script v6 indicators (7), strategies (2), combos (3) |
| `src/publishers/` | 3 | 211 | Telegram, Discord, JSON file signal publishers |
| `src/security/` | 2 | 62 | Input validator, audit log |
| `src/trading/core/` | 11 | 2,640 | Fetch scripts, SMC engine, signal push, build scripts |
| `src/trading/scrapers/` | 16 | 1,200+ | Yahoo, Stooq, Twelvedata, Finnhub, FRED, Alpha Vantage, CNN, seismic (USGS), comex (CME), intel_feed, chokepoints, vix_futures, crypto, agri_weather (Open-Meteo), shipping_intel (Baltic), oilgas_intel (energy) |
| `src/trading/backtesting/` | 9 | 1,998 | Engine, metrics, reports, data loader, models, 4 strategies |
| **Total src/** | **97** | **17,000+** | |
| `tests/unit/` | 48 | 14,500+ | 1,130+ test functions |
| `tests/integration/` | 23 | 4,200+ | API (14 route groups), DB, pipeline, backtest, provider, signal, competitor tests |
| `frontend/src/` | 33 | 7,000+ | 20 components + 3 macro sub-modules, 8 charts, SPA router, state, API client, live ticker |
| `frontend/src/__tests__/` | 26 | 3,200+ | 283 Vitest test cases |

## Commands

### Python
```bash
pytest                                  # Run all 1,258+ tests
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
cd frontend && npm test                 # Run 283 Vitest tests
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
python fetch_agri.py                    # Fetch agriculture weather + COT
python fetch_shipping.py                # Fetch shipping Baltic indices + routes
python fetch_oilgas.py                  # Fetch oil & gas intelligence
```

## API Routes

17 route groups registered in `src/api/app.py`:
- `health` -- `/health` (GET)
- `signals` -- `/api/signals` (GET)
- `instruments` -- `/api/instruments` (GET)
- `cot` -- `/api/cot` (GET)
- `macro` -- `/api/v1/macro` (GET: panel, indicators, vix-term, adr, regime-history)
- `webhook` -- `/api/webhook` (POST: push-alert, tv-alert)
- `backtests` -- `/api/v1/backtests` (GET: summary, trades, stats)
- `trading` -- `/api/v1/trading/*` (GET, POST: bot control, positions, signals, config, kill switch, calculate-size)
- `geointel` -- `/api/v1/geointel/*` (GET: seismic, comex, intel, chokepoints, regime, signals, events)
- `correlations` -- `/api/v1/correlations` (GET)
- `signal-log` -- `/api/v1/signal-log` (GET, POST, analytics)
- `prices` -- `/api/v1/prices/live` (GET: grouped live prices), `/api/v1/prices/{instrument}/history` (GET: daily close prices)
- `crypto` -- `/api/v1/crypto/market` (GET: 8-coin market overview), `/api/v1/crypto/fear-greed` (GET: Fear & Greed index)
- `signal-health` -- `/api/v1/signal-health` (GET: ensemble health, weights, decay alerts — live from pipeline_state)
- `risk` -- `/api/v1/risk` (GET: VaR, stress-test, correlation-matrix, regime-limits — live from pipeline_state)
- `pipeline` -- `/api/v1/pipeline` (GET: status, runs, gate-log; POST: approve, force-layer2)
- `journal` -- `/api/v1/journal` (GET: trade journal with reasoning, stats, filtering)

Middleware stack: CORS -> RateLimitMiddleware -> APIKeyMiddleware -> CSPMiddleware

Lifespan: APScheduler (6 jobs) starts/stops with the app when `SCHEDULER_ENABLED=1`

## Architecture Decisions (Sprint 3)

1. **Thin wrappers** -- 11 root-level scripts delegate to `src/trading/core/` and scrapers for backward compat. Each is <20 lines.
2. **Extracted analysis modules** -- `fetch_all.py` (was 800+ lines) now delegates to `src/analysis/` (scoring, levels, sentiment, setup_builder, technical, smc, cot_analyzer).
3. **Backtesting extracted** -- Engine split from 761 -> 278 lines. Metrics, reports, data_loader, models, and 4 strategy files pulled out.
4. **Provider pattern** -- `src/data/providers/base.py` defines abstract base; CFTC, Stooq, Yahoo implement it. `price_router.py` handles failover.
5. **Security at boundaries** -- `APIKeyMiddleware` + `RateLimitMiddleware` + `InputValidator` protect all API routes. `audit_log.py` for sensitive ops.
6. **SQLAlchemy + Alembic** -- Single SQLite DB via `src/db/engine.py`. All CRUD through `src/db/repository.py`. Migrations in `alembic/versions/`.
7. **Type hints everywhere** -- Full type annotations added across all `src/` modules. Validated with mypy.
8. **Agent prompt system** -- 36 YAML prompts in `src/agents/prompts/` (8 categories), loaded by `src/agents/registry.py`.

## Architecture Decisions (Week Sprint — Days 1-7)

9. **CSP + CORS hardening** -- Server-side CSP headers via CSPMiddleware + client-side CSP meta tag. CORS restricted to GET/POST with explicit headers.
10. **Input validation** -- InputValidator rejects (raises ValueError) instead of silently stripping dangerous patterns.
11. **Design tokens** -- `--sp-*`, `--fs-*`, `--radius-*`, `--ease` semantic tokens in `variables.css`. All inline font-family extracted to `.mono`/`.data-value` CSS classes.
12. **Lazy panel loading** -- 9 of 14 panels dynamic-imported on first tab switch. Index chunk reduced from ~150KB to 92.9KB (38%). Spinner skeleton shows during load.
13. **MacroPanel split** -- 550-line monolith → 142-line orchestrator + 3 sub-modules in `frontend/src/components/macro/` (DollarSmile, VixSection, InputsSection).
14. **WCAG 2.1 accessibility** -- `prefers-reduced-motion` disables all animation, ARIA tab pattern with keyboard nav, focus trap in COT modal, skip-to-content link, ▲/▼ colorblind prefixes on price changes.

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
- CoinGecko (free tier, no key, rate-limited)
- Alternative.me Fear & Greed (free, no key)

## Security
- API key auth: `SCALP_API_KEY` env var, constant-time comparison (hmac.compare_digest)
- TradingView webhook: `TV_WEBHOOK_SECRET` env var for payload verification
- Rate limiting: per-IP sliding window (60/min default), 10K IP memory cap
- XSS: escapeHtml() on all frontend API data rendering (CotChart, ScoreRadar, TopBar, all panels)
- CSP: server-side headers (CSPMiddleware in app.py) + client-side meta tag (index.html)
- CORS: restricted to GET/POST, explicit Content-Type + X-API-Key headers only
- Input validation: reject-on-danger pattern (ValueError, not silent strip)
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
