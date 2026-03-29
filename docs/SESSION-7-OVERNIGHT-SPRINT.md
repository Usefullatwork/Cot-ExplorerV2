# Session 7 — Overnight Sprint (9 hours, fully autonomous)

## Pickup Prompt

```
C:\Users\MadsF\Desktop\Cot-ExplorerV2:

## OVERNIGHT AUTONOMOUS SPRINT — Session 7 (9 hours, 12 phases)

You are running a fully autonomous overnight sprint. The user is sleeping.
Do NOT ask questions. Make decisions and keep moving. Use bypassPermissions on ALL agents.
Use mode: "auto" or "bypassPermissions" on every agent spawn.

### Context
- Branch: feature/session-6-geointel (PR #1 open, DO NOT merge)
- Create branch: feature/session-7-overnight from feature/session-6-geointel
- Python: C:\Users\MadsF\AppData\Local\Programs\Python\Python313\python.exe
- Git: use -m flag (HEREDOC hangs on Windows), stage files by name (never git add .)
- Tests: pytest tests/unit/ for backend, cd frontend && npx vitest --run for frontend
- Backend: 1,002 tests. Frontend: 158 tests. All passing.
- 19 DB tables, 44 API routes, 19-point scoring, 12 frontend tabs
- Reference site: https://snkpipefish.github.io/cot-explorer/
- Read CLAUDE.md before starting. Follow all existing patterns.

### Execution Rules (CRITICAL — read before any code)

1. Work in phases. Complete each phase fully (code + tests + commit + push) before next.
2. Run ALL tests after each phase. If tests fail, fix before moving on.
3. Use 5-10 parallel agents per phase (bypassPermissions on ALL).
4. Frontend: escapeHtml() on ALL API data. DM Mono for numbers. No new npm deps.
5. Backend: Pure functions in src/analysis/. Pydantic response models. Tests with mocks.
6. Commit after EACH phase. Push after each phase.
7. If stuck >15 min on anything, leave a TODO comment and move on.
8. Don't refactor working code. Don't touch Pepperstone adapter. Don't modify CI.
9. Stage files by name (never git add . or git add -A — timeouts).
10. Every new .py file needs a test_*.py. Every new .js component needs a *.test.js.

---

## BLOCK A: Feature Parity with Original (~3 hours)
Port everything the original cot-explorer has that V2 is missing.

### Phase 1: Enhanced Macro Panel
Agents: 4 parallel (dollar-smile, vix-term, rates-credit, safe-haven+adr)

1. **Dollar-Smile Model** — src/analysis/dollar_smile.py
   - classify_smile_state(dxy_5d, vix, yield_curve, growth_data) -> SmileState enum
   - 3 states: LEFT_SMILE (crisis, USD bid), BOTTOM (growth, USD weak), RIGHT_SMILE (risk-off, USD bid)
   - Frontend: 3-segment arc/bar showing active segment, below existing macro cards
   - Test: 10+ cases covering regime transitions

2. **VIX Term Structure** — src/trading/scrapers/vix_futures.py
   - Fetch VIX spot + 9-day + 3-month from CBOE delayed data (public, no key)
   - Compute contango/backwardation regime
   - API: GET /api/v1/macro/vix-term
   - Frontend: 3 values + regime badge in MacroPanel
   - Test: mock CBOE response, test contango/backwardation logic

3. **Interest Rate & Credit Grid** — 8 metric boxes
   - Backend: GET /api/v1/macro/rates — aggregate from existing FRED data + macro_snapshots
   - Cards: 10Y yield, 3M yield, yield curve (10Y-3M), HY spreads, TIPS 5d, Copper 5d, EM momentum, Fed Funds
   - Color coding: green=improving, red=deteriorating, gray=neutral
   - Frontend: Grid layout below Dollar-Smile

4. **Safe-Haven Hierarchy + Session Ranges**
   - Safe-Haven: Pure frontend card, content driven by VIX regime
   - Session Ranges: GET /api/v1/macro/adr — calculate 20-day ADR from prices_daily
   - Frontend: ADR table with instrument, ADR value, ADR as % of price

### Phase 2: Rich Setup Cards (replace basic CotTable)
Agents: 3 parallel (backend enrichment, frontend cards, tests)

1. **Setup Statistics Bar** — A+ count, A count, B count, MAKRO count, binary risk warnings
2. **Collapsible Setup Cards** per instrument:
   - Header: grade badge, score bar (filled %), instrument, timeframe bias, LONG/SHORT indicator
   - Body (expandable): entry/SL/T1/T2 levels, R:R ratios, key stats, COT mini-sparkline
   - Score breakdown: 19 dots (filled=pass, empty=fail) with tooltip labels
3. **Setup Filters** — filter by grade, timeframe, instrument class
4. **Sparkline renderer** — renderSparkline(values[], opts) -> inline SVG string. 60x20px. Reusable.

### Phase 3: Enhanced COT Panel (accordion + sparklines + modal)
Agents: 3 parallel (accordion UI, modal, tests)

1. **Category Accordion** — 8 groups matching original:
   - Aksjer, Valuta, Renter, Ravarer, Landbruk, Krypto, Volatilitet, Annet
   - Header: emoji, name, stacked bull/neutral/bear bar, count badges
   - Body: grid of market cards with signal badge, net %, sparkline
2. **COT Detail Modal** — click market card:
   - Bar chart: speculator net position over time (canvas or SVG)
   - Stats row: 6 boxes (net now, weekly change, % OI, hist max, hist min, data points)
   - Price overlay line chart (if price data available)
3. **COT Search** — text filter across all categories

### Phase 4: Prices Panel (new tab #13)
Agents: 2 parallel (backend + frontend)

1. **GET /api/v1/prices/live** — latest price + 1d/5d changes for all instruments
2. **3 card groups**: Indices (SPX, NAS100, VIX), Forex (EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CHF, DXY), Commodities (Gold, Silver, Brent, WTI, NATGAS)
3. **Each card**: name, current price (DM Mono), 1d change (colored), 5d change
4. **Auto-refresh**: poll every 60s if tab active

---

## BLOCK B: Beyond the Original (~3 hours)
New features the original does NOT have. This is where V2 becomes genuinely better.

### Phase 5: Backtesting Visualization Dashboard
Agents: 3 parallel (equity curve, stats, drawdown)

1. **New tab: Backtest (#14)** — dedicated backtesting results visualization
2. **Equity Curve Chart** — canvas-based line chart from backtest_results
   - X: trade number, Y: cumulative PnL (pips or USD)
   - Color regions: green for winning streaks, red for drawdowns
3. **Performance Stats Grid** — 12 metrics:
   - Total trades, win rate, avg win, avg loss, profit factor, max drawdown
   - Sharpe ratio, Sortino, avg RR, best trade, worst trade, avg duration
4. **Per-Instrument Breakdown** — table: instrument, trades, win rate, avg PnL, total PnL
5. **Grade Analysis** — bar chart: trades per grade, win rate per grade
6. **Backend**: GET /api/v1/backtests/stats — aggregate from backtest_results table

### Phase 6: Position Sizing Calculator
Agents: 2 parallel (backend logic + frontend)

1. **src/trading/bot/lot_sizing.py** already exists — expose via API
2. **GET /api/v1/trading/calculate-size** — account balance, risk %, instrument, SL distance -> lot size
3. **Frontend panel** (inside Trading tab, not new tab):
   - Input fields: account balance, risk %, instrument dropdown, SL pips
   - Output: lot size, pip value, max loss in USD, position value
   - VIX regime adjusts suggested lot tier (full/half/quarter)

### Phase 7: Historical Regime Timeline
Agents: 2 parallel (backend + frontend)

1. **Regime History** — store regime changes in macro_snapshots or new lightweight table
2. **Timeline visualization** in MacroPanel:
   - Horizontal bar chart, last 30 days
   - Color segments: green=normal, yellow=risk-off, orange=energy-shock, red=crisis/war
   - Hover shows date + regime + trigger event
3. **Backend**: GET /api/v1/macro/regime-history — last N days of regime transitions

### Phase 8: Signal Replay + Advanced Analytics
Agents: 3 parallel (replay engine, analytics, frontend)

1. **Signal Replay** — play through historical signals on a timeline
   - Slider: date range selector
   - Step through: shows each signal's entry, progression, exit
   - Display: instrument, grade, entry, outcome, PnL
2. **Performance Analytics** (extend SignalLogPanel):
   - By instrument: heatmap of hit rates per instrument
   - By time: hit rate by hour of day, day of week
   - By regime: hit rate per VIX regime
   - Streak analysis: longest win/loss streaks
3. **Backend**: GET /api/v1/signal-log/analytics — aggregated performance breakdowns

---

## BLOCK C: Technical Debt + Quality (~2 hours)
Fix the adversarial review findings and harden the platform.

### Phase 9: Alembic Migration + DB Hardening
Agents: 2 parallel (migration + dedup constraints)

1. **Alembic migration** for 5 new tables (Session 6):
   - seismic_events, comex_inventory, geointel_articles, signal_performance, correlation_snapshots
   - Command: alembic revision --autogenerate -m "add geo-intel and performance tables"
   - Verify: alembic upgrade head on fresh DB

2. **Dedup constraints**:
   - geointel_articles: UniqueConstraint on (url, category)
   - seismic_events: UniqueConstraint on (event_time, place)
   - Update _store_* helpers to use INSERT OR IGNORE / merge pattern

3. **FK cascade**: Add ondelete="CASCADE" to SignalPerformance.signal_id

### Phase 10: Live Fetch Hardening
Agents: 2 parallel (caching + session scope)

1. **Request coalescing for ?live=true**:
   - Add a TTL cache (60s) for live fetches — if data was fetched <60s ago, return cached
   - Prevents triple-fetch when frontend calls 3 geo-intel endpoints in parallel
   - Simple module-level dict with timestamp: src/api/middleware/fetch_cache.py

2. **Session scope refactor** (ONLY for new route files):
   - Replace manual gen.send()/gen.throw() with context manager in:
     - src/api/routes/geointel.py
     - src/api/routes/correlations.py
     - src/api/routes/signal_log.py
   - Pattern: with session_scope() as session: ...
   - DO NOT touch existing working routes (signals.py, cot.py, etc.)

3. **Keyword boundary matching** for chokepoints + region detection:
   - chokepoints.py: Use word boundary check (f" {kw} " or regex \b)
   - impact_mapper.py: Same for region detection

### Phase 11: Chart Library + Data Viz Foundation
Agents: 2 parallel (chart utils + integration)

1. **Lightweight chart rendering utilities** — frontend/src/charts/
   - barChart(container, data[], opts) — vertical bars (for COT history, grade breakdown)
   - lineChart(container, data[], opts) — line with fill (for equity curves, price overlay)
   - heatmapCell(value, min, max) — colored cell for correlation matrix + analytics
   - sparkline(values[], opts) — inline SVG for COT cards, setup cards
   - All canvas-based or SVG. Zero dependencies. <200 lines each.

2. **Integrate** into:
   - COT modal (bar chart)
   - Backtest dashboard (equity curve, grade bars)
   - Setup cards (sparklines)
   - Correlation panel (heatmap cells)

---

## BLOCK D: Documentation + Ship (~1 hour)

### Phase 12: Documentation + Final Ship
Agent: 1

1. **Update CLAUDE.md** with all new modules, routes, tests, tabs
2. **Write docs/SESSION-7-RESULTS.md** with:
   - What was built per phase
   - Test counts (before/after)
   - Files changed
   - What was skipped and why
   - Known issues
3. **Run /gstack-review** on the full diff
4. **Fix any AUTO-FIX findings**
5. **Final test run** — all backend + frontend
6. **Push final state**
7. **Create PR #2** against feature/session-6-geointel (or main if PR #1 was merged)

---

## Target Metrics (end of sprint)

| Metric | Before | Target |
|--------|--------|--------|
| Frontend tabs | 12 | 14 (+ Priser, Backtest) |
| Frontend components | 15 | 25+ |
| Backend modules (src/analysis) | 13 | 16+ |
| API endpoints | 44 | 55+ |
| Backend tests | 1,002 | 1,200+ |
| Frontend tests | 158 | 250+ |
| Chart components | 4 | 8+ |
| DB tables | 19 | 19 (no new tables, just migration + constraints) |

## Decision Matrix (for autonomous choices)

| Decision | Default Choice |
|----------|---------------|
| Canvas vs SVG for charts | SVG for small (<100 points), Canvas for large |
| New tab vs extend existing | Extend existing unless >3 new sections |
| Mock external API vs skip | Always mock, never skip tests |
| Feature incomplete vs skip | Ship what works, TODO for the rest |
| Norwegian vs English labels | Norwegian (match existing: Setups, Makro, Priser) |
| Polling interval | 60s for prices, 300s for macro, 600s for COT |
| Error handling in scrapers | Return empty + log.error (never crash) |
| Chart animation | None. Static renders. Performance > flair. |
```

## Phase Timing Estimate

| Phase | Est. Time | Agents | Cumulative |
|-------|-----------|--------|------------|
| 1. Enhanced Macro | 45 min | 4 | 0:45 |
| 2. Rich Setup Cards | 45 min | 3 | 1:30 |
| 3. Enhanced COT | 40 min | 3 | 2:10 |
| 4. Prices Panel | 25 min | 2 | 2:35 |
| 5. Backtest Dashboard | 50 min | 3 | 3:25 |
| 6. Position Calculator | 20 min | 2 | 3:45 |
| 7. Regime Timeline | 30 min | 2 | 4:15 |
| 8. Signal Analytics | 45 min | 3 | 5:00 |
| 9. DB Hardening | 30 min | 2 | 5:30 |
| 10. Live Fetch Fix | 30 min | 2 | 6:00 |
| 11. Chart Library | 40 min | 2 | 6:40 |
| 12. Docs + Ship | 30 min | 1 | 7:10 |
| Buffer for retries | ~1:50 | — | **9:00** |
