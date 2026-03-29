# Session 8 Results — Feature Parity Sprint

**Branch**: `feature/session-8-parity`
**Date**: 2026-03-29
**Tests**: 1,190 backend + 232 frontend = **1,422 total** (all passing)

## Changes

### Phase 0: Bug Fixes
- Removed unused `case` import from `signal_log.py`
- Fixed `test_pipeline.py` sys.modules poisoning (MagicMock replacing real `src.security` package)
- Fixed `test_api_cot.py` fixture missing required `date` and `report_type` fields

### Phase 1: COT Sparklines
- Added timeseries cache to `/api/v1/cot` endpoint
- Loads `data/timeseries/{symbol}_{report}.json` files on first request
- Injects last 20 `spec_net` values as `cot_history` per market
- Frontend already handles rendering via `svgSparkline.js`

### Phase 2: Price Overlay in COT Modal
- New endpoint: `GET /api/v1/prices/{instrument}/history`
- Added `createPriceChart` (lightweight-charts) below COT bar chart in modal
- Maps 13 CFTC contract codes to price instrument keys
- Chart auto-hides when no price data available

### Phase 3: Krypto Intel Tab
- New scraper: `src/trading/scrapers/crypto.py` (CoinGecko + alternative.me)
- New route: `src/api/routes/crypto.py` (market + fear-greed endpoints, 120s/300s cache)
- New panel: `frontend/src/components/CryptoPanel.js`
- Fear & Greed gauge, total market cap, BTC dominance, 8-coin price grid
- Full wiring: router, TopBar, main.js, state, api.js
- 9 backend tests + 8 frontend tests

### Phase 4: Missing Price Instruments
- Added USDNOK to Valuta group
- Added Rente/Kreditt group with HYG and TIP

### Phase 5: Vitest OOM Fix
- Added `pool: 'forks'` with `singleFork: true` to vite.config.js
- Prevents Windows OOM crashes during test runs

## Files Changed

| Action | Count |
|--------|-------|
| Modified | 12 |
| Created | 6 |

### New Files
- `src/trading/scrapers/crypto.py`
- `src/api/routes/crypto.py`
- `frontend/src/components/CryptoPanel.js`
- `frontend/src/__tests__/CryptoPanel.test.js`
- `tests/unit/test_crypto.py`
- `docs/SESSION-8-RESULTS.md`

## Summary
- **14 frontend tabs** (was 13), **52 API endpoints** (was 51)
- **1,422 tests** (was 1,260)
- ~99% feature parity with original v1
