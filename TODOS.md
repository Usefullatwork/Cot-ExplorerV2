# TODOS — Cot-ExplorerV2

## Phase 0 Prerequisites

### Fix 58 failing integration tests
- **What:** Resolve `src.security` package resolution that breaks 58 integration tests
- **Why:** Broken test suite erodes trust in results. Can't tell if Phase 1a changes break something new when 58 tests are already red. Security middleware is critical for multi-tenant.
- **Context:** Pre-existing issue, not from deep review sprint. The `src.security` module imports fail in integration test context. Likely a `__init__.py` or `sys.path` issue.
- **Depends on:** Nothing. Can fix independently.

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
