# Session 7 — Overnight Sprint: Feature Parity with Original Cot-Explorer

## Pickup Prompt

```
C:\Users\MadsF\Desktop\Cot-ExplorerV2:

## OVERNIGHT AUTONOMOUS SPRINT — Session 7

You are running a fully autonomous overnight sprint. The user is sleeping.
Do NOT ask questions. Make decisions and keep moving. Use bypassPermissions on ALL agents.

### Context
- Branch: feature/session-6-geointel (PR #1 open, DO NOT merge — work on a NEW branch)
- Create branch: feature/session-7-feature-parity from feature/session-6-geointel
- Python: C:\Users\MadsF\AppData\Local\Programs\Python\Python313\python.exe
- Git: use -m flag (HEREDOC hangs on Windows), stage files by name (never git add .)
- Tests: pytest tests/unit/ for backend, cd frontend && npx vitest --run for frontend
- Backend: 1,002 tests. Frontend: 158 tests. All passing.
- 19 DB tables, 44 API routes, 19-point scoring, 12 frontend tabs

### What to build — Feature parity with https://snkpipefish.github.io/cot-explorer/

The original site has features V2 is missing. Port them in priority order.
Reference the original's data files: data/macro/latest.json, data/combined/latest.json, data/prices/*.

#### PHASE 1: Enhanced Macro Panel (highest value, builds on existing MacroPanel)
Agents: 3 parallel (backend data, frontend UI, tests)

1. **Dollar-Smile Model** — 3-segment visualization (Risk-Off USD / Growth USD / Crisis USD)
   - Backend: Add dollar_smile_state() to src/analysis/ that classifies current regime
   - Frontend: Visual 3-segment bar showing which segment is active, with labels
   - Data: Uses DXY, VIX, yield curve already in macro_snapshots table

2. **VIX Term Structure** — Spot vs forward contracts with contango/backwardation label
   - Backend: New src/trading/scrapers/vix_futures.py — fetch VIX 9D + 3M from CBOE
   - Frontend: Display spot, 9D, 3M values with regime label (contango/backwardation)
   - Add to existing MacroPanel below the VIX card

3. **Interest Rate & Credit Panel** — 8 metric boxes in a grid
   - 10Y yield, 3M yield, yield curve (10Y-3M), HY spreads, TIPS 5d, Copper 5d, EM momentum, Fed Funds
   - Backend: Most data already in FRED scraper — wire to new API endpoint
   - Frontend: Grid of color-coded metric cards (green=positive, red=negative)

4. **Safe-Haven Hierarchy** — Text card showing currency positioning guidance
   - Pure frontend — static content card driven by VIX regime
   - "Risk-Off: JPY > CHF > USD > Gold" / "Risk-On: AUD > NZD > CAD > GBP"

5. **Session Ranges** — ADR (Average Daily Range) table per instrument
   - Backend: Calculate 20-day ADR from prices_daily table
   - Frontend: Table with instrument, ADR value, ADR as % of price

#### PHASE 2: Enhanced Setups Panel (replaces existing CotTable with rich setup cards)
Agents: 3 parallel (backend, frontend, tests)

1. **Setup Cards** — Collapsible instrument cards showing:
   - Grade badge (A+/A/B/C), score bar with fill, timeframe bias label
   - LONG/SHORT/NEUTRAL bias indicator
   - Current price, session status, binary risk flag
   - Expandable detail: entry/SL/T1/T2 levels, R:R ratios, resistance/support with ATR distance
   - COT mini-sparkline (last 20 weeks net position)
   - Score breakdown dots (19 criteria, filled/empty)

2. **Setup Statistics Bar** — Top-of-panel count cards: A+ setups, B setups, MAKRO, binary risk warnings

3. **Setup Filters** — Filter by grade, timeframe bias, instrument class

#### PHASE 3: Enhanced COT Panel (accordion with sparklines + modal)
Agents: 2 parallel (frontend + tests)

1. **Category Accordion** — 8 groups (Stocks, Currency, Rates, Commodities, Agriculture, Crypto, Volatility, Other)
   - Each group header: emoji, name, stacked bull/neutral/bear bar, count badges
   - Expandable: grid of market cards with signal strength badge, net %, sparkline

2. **COT Detail Modal** — Click a market card to open a modal:
   - Bar chart: historical speculator net position (color-coded by direction)
   - Stats row: net now, weekly change, % of OI, historical max/min, data points
   - Price overlay chart (when price data available)
   - Interpretation text

#### PHASE 4: Prices Panel (new tab)
Agents: 2 parallel (frontend + backend endpoint)

1. **Grouped Price Cards** — 3 groups: Indices, Forex, Commodities
   - Each card: instrument name, current price, 1d change (colored), 5d change
   - Use existing prices_daily table + live ticker data

2. **Wire to router** — Add Priser tab (#11 in navigation, before Geo-Signaler)

#### PHASE 5: Polish + Sparkline Library
Agent: 1

1. **Sparkline rendering** — Inline SVG sparklines for COT cards and setup cards
   - Pure JS, no library dependency. 60x20px inline SVGs.
   - Function: renderSparkline(values[], {width, height, color}) -> SVG string

2. **Score Breakdown Dots** — 19 dots (filled green / empty gray) showing which criteria passed
   - Reusable function: renderScoreDots(details[]) -> HTML string

### Execution Rules

1. Work in phases. Complete Phase 1 fully (code + tests + working) before Phase 2.
2. Commit after EACH phase with descriptive message.
3. Run ALL tests after each phase. If tests fail, fix before moving on.
4. Use 5-8 parallel agents per phase (bypassPermissions on ALL).
5. Backend data: Use existing scrapers and DB tables where possible. Only create new scrapers for VIX futures.
6. Frontend: Follow existing patterns — escapeHtml() on ALL API data, DM Mono for numbers, DM Sans for text.
7. All new API endpoints under /api/v1/ and registered in src/api/app.py.
8. All new Python files need corresponding test files in tests/unit/.
9. All new JS components need test files in frontend/src/__tests__/.
10. DO NOT touch existing passing tests. Only add new ones.
11. If stuck on a phase for >15 min, skip to next phase and leave a TODO.
12. Push after each phase: git push origin feature/session-7-feature-parity

### Target Metrics
- New frontend components: 5+ (DollarSmile, VixTermStructure, SetupCards, CotAccordion, PricesPanel)
- New backend modules: 3+ (dollar_smile, vix_futures scraper, adr calculator)
- New tests: 100+ (maintain >1,100 backend, >200 frontend)
- New API endpoints: 5+ (macro/rates, macro/dollar-smile, macro/adr, macro/vix-term, prices/live)

### What NOT to do
- Don't refactor existing working code
- Don't change the DB schema (use existing 19 tables)
- Don't touch Pepperstone adapter
- Don't modify CI/CD workflows
- Don't create new npm dependencies (vanilla JS only)

### Final Step
After all phases, run /gstack-review and commit fixes. Then push and leave a summary in docs/SESSION-7-RESULTS.md.
```

## Feature Gap Analysis (V2 vs Original)

| Feature | Original | V2 Status | Sprint Phase |
|---------|----------|-----------|--------------|
| Dollar-Smile Model | 3-segment viz | MISSING | Phase 1 |
| VIX Term Structure | Spot/9D/3M + regime | MISSING | Phase 1 |
| Interest Rate & Credit | 8 metric boxes | MISSING | Phase 1 |
| Safe-Haven Hierarchy | Text card by regime | MISSING | Phase 1 |
| Session Ranges (ADR) | Table per instrument | MISSING | Phase 1 |
| Rich Setup Cards | Expandable + sparklines | Basic CotTable | Phase 2 |
| Setup Statistics Bar | A+/B/MAKRO counts | MISSING | Phase 2 |
| COT Accordion | 8 category groups | Flat table | Phase 3 |
| COT Sparklines | Inline mini-charts | MISSING | Phase 3 |
| COT Detail Modal | Historical chart + stats | MISSING | Phase 3 |
| Price Panel | Grouped cards | No dedicated tab | Phase 4 |
| Score Breakdown Dots | 19 filled/empty dots | MISSING | Phase 5 |
| Ticker Bar | Scrolling prices | DONE (Session 6) | - |
| Correlation Heatmap | Matrix table | DONE (Session 6) | - |
| Signal Log | Stats + table | DONE (Session 6) | - |
| Geo-Intel panels | 4 panels + regime | DONE (Session 6) | - |
| Calendar | High/Medium events | DONE (Session 4) | - |

## Architecture Notes for the Sprint

### Existing patterns to follow:
- `frontend/src/components/*.js` — export render(container) + update(data)
- `frontend/src/api.js` — export async fetch functions using get/post helpers
- `frontend/src/state.js` — setState(key, value) triggers subscribed panel updates
- `src/api/routes/*.py` — FastAPI routers with Pydantic response models
- `src/analysis/*.py` — Pure functions, no side effects, Pydantic I/O
- `tests/unit/test_*.py` — pytest with unittest.mock for external calls
- `frontend/src/__tests__/*.test.js` — vitest with jsdom, vi.fn() mocks

### Data already available in DB:
- prices_daily: OHLCV for all 17 instruments
- macro_snapshots: VIX, DXY, yield curve, fear_greed, news_sentiment
- fundamentals: GDP, CPI, employment, rates (via FRED)
- cot_positions: All CFTC data (4 report types)
- signals: Generated signals with score_details JSON
