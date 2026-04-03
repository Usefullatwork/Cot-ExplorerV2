# Known Issues — v2.1.0-rc1

## Pipeline

- **Broker adapter is placeholder**: Pepperstone cTrader endpoints are mocked in `src/trading/bot/broker/paper.py`. A+ auto-execution creates a paper position, not a real order.
- **Delayed execution (A-tier)**: Relies on APScheduler one-shot jobs for 15-minute re-check. Not tested under process crash or restart scenarios.
- **No frontend pipeline tab**: Pipeline monitoring is API-only (`/api/v1/pipeline/*`). A dashboard tab is planned for v2.2.

## V1 Scrapers

- **Google News RSS rate limiting**: Enforces 2s delay between category fetches (same as `intel_feed.py`), but Google may still rate-limit aggressively under heavy use.
- **Open-Meteo free tier**: 10,000 API calls/day limit. With 14 regions and 2h intervals, daily usage is ~112 calls — well within limits.
- **Stooq availability**: Baltic index data from Stooq can be delayed or unavailable outside European market hours.

## Risk Management

- **Kelly sizing fallback**: When no trade history exists for an instrument, Kelly returns 0 and falls back to the VIX x grade matrix (`lot_sizing.py`). This is conservative but means new instruments always start at manual approval (B-tier).
- **Correlation matrix**: Computed from PriceDaily (daily closes), not intraday data. May miss short-term correlation shifts.
- **Account equity**: Currently derived from `BotConfig.risk_pct * 100,000` as a proxy. Real equity tracking requires broker API integration.

## Database

- **pipeline_state is single-row**: Works well for SQLite but would need redesign for multi-tenant or sharded deployments.
- **APScheduler job store**: Creates its own `apscheduler_jobs` table via SQLAlchemyJobStore. Compatible with SQLite WAL mode but untested under high concurrency.
