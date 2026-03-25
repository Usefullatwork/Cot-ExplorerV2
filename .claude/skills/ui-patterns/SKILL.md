---
name: ui-patterns
description: CSS design system, component patterns, and API contracts for the Cot-ExplorerV2 dashboard
user-invocable: false
---

# UI Patterns — Cot-ExplorerV2

## CSS Custom Properties (exact v1 values)

```css
:root {
  --bg: #0d1117;      /* Page background */
  --s: #161b22;       /* Surface (cards, topbar) */
  --s2: #1c2128;      /* Surface secondary (hover) */
  --b: #21262d;       /* Border */
  --b2: #30363d;      /* Border secondary */
  --t: #e6edf3;       /* Text primary */
  --m: #7d8590;       /* Text muted */
  --bull: #3fb950;    /* Bullish / positive */
  --bbg: rgba(63, 185, 80, 0.12);
  --bear: #f85149;    /* Bearish / negative */
  --rbg: rgba(248, 81, 73, 0.12);
  --warn: #d29922;    /* Warning / neutral */
  --wbg: rgba(210, 153, 34, 0.12);
  --blue: #58a6ff;    /* Accent / active */
  --blbg: rgba(88, 166, 255, 0.12);
}
```

## Font Stack
- Body: `'DM Sans', sans-serif` (400, 500, 600)
- Numbers/Prices: `'DM Mono', monospace` (400, 500)
- Logo: `'Playfair Display', serif` (700, italic 400)
- Google Fonts CDN in index.html `<head>`

## Component Pattern

Each component is a vanilla JS ES module:

```js
// components/ExamplePanel.js
export function render(container, data) {
  container.innerHTML = `<div class="card">...</div>`;
  // Attach event listeners after innerHTML
}
```

## Grid Systems
- `.g4` — 4 columns
- `.g3` — 3 columns
- `.g2` — 2 columns (equal)
- `.g21` — 2:1 ratio

## API Endpoints (FastAPI at /api/v1/)

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/v1/signals` | GET | Signal[] (filterable: grade, min_score, direction, instrument, limit) |
| `/api/v1/signals/{key}` | GET | Signal detail |
| `/api/v1/instruments` | GET | Instrument[] (12 items from YAML) |
| `/api/v1/instruments/{key}` | GET | Instrument + current_price |
| `/api/v1/cot` | GET | COT position[] |
| `/api/v1/cot/{symbol}/history` | GET | COT timeseries (start, end, report_type) |
| `/api/v1/cot/summary` | GET | {top_movers, extremes} |
| `/api/v1/macro` | GET | Full macro panel (Dollar Smile, VIX, conflicts) |
| `/api/v1/macro/indicators` | GET | {HYG, TIP, TNX, IRX, Copper, EEM} |
| `/health` | GET | {status, version, last_run, timestamp} |
| `/metrics` | GET | {signals, prices_daily, cot_positions} counts |
