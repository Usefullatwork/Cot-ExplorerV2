# TODOS — Cot-ExplorerV2

## Phase 0 Prerequisites

### ~~Fix 58 failing integration tests~~ ✅ DONE (Session 8)

### Verify cTrader API type (REST vs gRPC)
- **What:** Research whether Pepperstone's cTrader Open API is REST (httpx) or gRPC/protobuf (grpcio)
- **Why:** Current adapter assumes REST endpoints. If cTrader is gRPC-only, the adapter needs a complete rearchitect. Also check if MetaAPI.cloud bridge provides REST over cTrader.
- **Context:** Outside voice flagged this. cTrader Open API documentation is at https://help.ctrader.com/open-api/. Must verify BEFORE any Phase 0 broker adapter work.
- **Depends on:** Nothing. Research task only.

## Phase 1a Items

### Postgres connection pool sizing
- **What:** Configure SQLAlchemy async pool_size = max_users * 2 (minimum 20) or use PgBouncer for connection pooling
- **Why:** Default pool (5 connections) will exhaust with 10+ concurrent bot coroutines doing DB writes. Connection exhaustion causes bot coroutines to hang, defeating the async isolation model.
- **Context:** Part of SQLite → PostgreSQL migration in Phase 1a. Use `create_async_engine(pool_size=20, max_overflow=10)`.
- **Depends on:** Phase 1a async rewrite + Postgres migration.

### Cache stampede lock for shared data pipeline
- **What:** Implement lock-before-fetch pattern for cached data sources (COT, FRED, sentiment)
- **Why:** When sentiment cache expires (15-min TTL), the next request triggers a fresh fetch. If 10 users' bots check simultaneously, only the first should fetch; rest should wait on lock.
- **Context:** Redis (already planned) provides SETNX-based distributed locks. Pattern: `if not cached: acquire lock → fetch → cache → release lock`.
- **Depends on:** Redis integration in Phase 1a.

## Session 9 Findings (2026-03-29)

### Timeseries sparklines require historical data
- **What:** `build_timeseries.py` requires MIN_WEEKS=10 data points. With only 1 weekly snapshot, no sparklines are generated.
- **Fix:** Run `python fetch_cot.py --history` once to download historical COT data (2006-present). This populates `data/cot/history/` which `build_timeseries.py` reads.
- **Impact:** COT table sparklines will be empty until history is fetched.

### FRED API key not configured
- **What:** `fetch_fundamentals.py` skips all indicators without a FRED API key.
- **Fix:** Get a free key from https://fred.stlouisfed.org/docs/api/api_key.html and set `FRED_API_KEY` in `.env`.
- **Impact:** Fundamental scores are neutral (0.0) without the key. Scoring still works but misses macro data.

### DB tables largely unused
- **What:** 19 SQLite tables defined but only used by trading bot routes. All data flows through JSON files.
- **Context:** Session 9 added JSON fallbacks for signals and prices routes. DB persistence can be added in Phase 1a when migrating to Postgres.
- **Not a bug:** Designed this way — JSON is the primary data store, DB is for bot state.
