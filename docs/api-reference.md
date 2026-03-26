# API Reference

Cot-ExplorerV2 exposes a FastAPI application with automatic Swagger UI at `/docs` and ReDoc at `/redoc`.

**Base URL:** `http://localhost:8000`

## Authentication

If the environment variable `SCALP_API_KEY` is set, all `/api/v1/*` routes require an `X-API-Key` header. When the variable is unset or empty the API runs in **public mode** (no auth).

```
X-API-Key: <your-api-key>
```

Rate limiting is enforced per IP. Default: 60 requests/minute (configurable via `RATE_LIMIT_PER_MINUTE`).

---

## Endpoints

### Health & Metrics

#### GET /health

Health check returning service status, API version, and last signal run timestamp.

**Tags:** `health`

| Field       | Type            | Description                                      |
|-------------|-----------------|--------------------------------------------------|
| `status`    | `string`        | Service status (`"ok"`)                          |
| `version`   | `string`        | API version (e.g. `"2.0.0"`)                    |
| `last_run`  | `string \| null` | ISO timestamp of most recent signal generation  |
| `timestamp` | `string`        | Current server UTC timestamp                     |

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "version": "2.0.0",
  "last_run": "2026-03-25T14:30:00+00:00",
  "timestamp": "2026-03-26T08:00:00+00:00"
}
```

---

#### GET /health/detailed

Comprehensive system diagnostics including uptime, DB size, row counts, last pipeline run, and process memory.

**Tags:** `health`

| Field                  | Type           | Description                              |
|------------------------|----------------|------------------------------------------|
| `status`               | `string`       | Service status                           |
| `version`              | `string`       | API version                              |
| `timestamp`            | `string`       | Current server UTC timestamp             |
| `uptime_seconds`       | `float`        | Seconds since process started            |
| `started_at`           | `string`       | UTC timestamp of process start           |
| `db_size_mb`           | `float \| null` | SQLite file size in MB                  |
| `db_tables`            | `int \| null`  | Number of DB tables                      |
| `last_pipeline_run`    | `string \| null` | Last pipeline_start audit timestamp    |
| `last_signal_generated`| `string \| null` | Most recent signal timestamp           |
| `total_signals`        | `int`          | Total signal count                       |
| `total_prices`         | `int`          | Total daily price bar count              |
| `total_cot`            | `int`          | Total COT position count                 |
| `memory_rss_mb`        | `float \| null` | Process RSS memory in MB               |

```bash
curl http://localhost:8000/health/detailed
```

---

#### GET /metrics

Database row counts for core tables.

**Tags:** `health`

| Field            | Type  | Description                           |
|------------------|-------|---------------------------------------|
| `signals`        | `int` | Total trading signals stored          |
| `prices_daily`   | `int` | Total daily price bars                |
| `cot_positions`  | `int` | Total COT position records            |

```bash
curl http://localhost:8000/metrics
```

```json
{
  "signals": 142,
  "prices_daily": 5840,
  "cot_positions": 1200
}
```

---

### Signals

#### GET /api/v1/signals

List trading signals with optional filters.

**Tags:** `signals`

**Query Parameters:**

| Parameter     | Type   | Default | Description                          |
|---------------|--------|---------|--------------------------------------|
| `grade`       | string | null    | Filter by grade: A+, A, B, C        |
| `timeframe`   | string | null    | Filter by timeframe bias             |
| `min_score`   | int    | null    | Minimum confluence score (0-12)      |
| `direction`   | string | null    | Trade direction: `bull` or `bear`    |
| `active_only` | bool   | false   | Only signals at entry level now      |
| `instrument`  | string | null    | Filter by instrument key             |
| `limit`       | int    | 100     | Max results (1-500)                  |

```bash
curl "http://localhost:8000/api/v1/signals?grade=A&min_score=8&limit=10"
```

```json
[
  {
    "id": 42,
    "instrument": "EURUSD",
    "generated_at": "2026-03-25T14:30:00+00:00",
    "direction": "bull",
    "grade": "A",
    "score": 10,
    "timeframe_bias": "SWING",
    "entry_price": 1.085,
    "stop_loss": 1.079,
    "target_1": 1.095,
    "target_2": 1.102,
    "rr_t1": 1.67,
    "rr_t2": 2.83,
    "vix_regime": "normal",
    "pos_size": "full",
    "at_level_now": true,
    "score_details": [{"label": "SMA200", "passes": true}]
  }
]
```

---

#### GET /api/v1/signals/{key}

Latest signal for a specific instrument.

**Tags:** `signals`

| Path Parameter | Type   | Description       |
|---------------|--------|-------------------|
| `key`         | string | Instrument key    |

```bash
curl http://localhost:8000/api/v1/signals/EURUSD
```

Returns the same `SignalResponse` shape as the list endpoint.

---

### Instruments

#### GET /api/v1/instruments

List all tracked instruments with their configuration.

**Tags:** `instruments`

```bash
curl http://localhost:8000/api/v1/instruments
```

```json
[
  {
    "key": "EURUSD",
    "name": "EUR/USD",
    "symbol": "EURUSD=X",
    "label": "EUR/USD",
    "category": "valuta"
  }
]
```

---

#### GET /api/v1/instruments/{key}

Single instrument detail with the latest daily price from the database.

**Tags:** `instruments`

| Path Parameter | Type   | Description       |
|---------------|--------|-------------------|
| `key`         | string | Instrument key    |

```bash
curl http://localhost:8000/api/v1/instruments/EURUSD
```

```json
{
  "key": "EURUSD",
  "name": "EUR/USD",
  "symbol": "EURUSD=X",
  "label": "EUR/USD",
  "category": "valuta",
  "current_price": {
    "date": "2026-03-25",
    "high": 1.092,
    "low": 1.081,
    "close": 1.088,
    "source": "yahoo"
  }
}
```

---

### COT Data

#### GET /api/v1/cot

All latest COT positions from the combined data file.

**Tags:** `cot`

```bash
curl http://localhost:8000/api/v1/cot
```

Returns `list[CotPositionResponse]` with fields: `date`, `symbol`, `market`, `report_type`, `open_interest`, `change_oi`, `spec_long`, `spec_short`, `spec_net`, `comm_long`, `comm_short`, `comm_net`, `nonrept_long`, `nonrept_short`, `nonrept_net`, `change_spec_net`, `category`.

---

#### GET /api/v1/cot/{symbol}/history

Time series of COT positions for a CFTC contract symbol.

**Tags:** `cot`

**Query Parameters:**

| Parameter     | Type   | Default | Description                                    |
|---------------|--------|---------|------------------------------------------------|
| `start`       | string | null    | Start date (YYYY-MM-DD)                        |
| `end`         | string | null    | End date (YYYY-MM-DD)                          |
| `report_type` | string | null    | tff, legacy, disaggregated, or supplemental    |

```bash
curl "http://localhost:8000/api/v1/cot/099741/history?start=2026-01-01&report_type=tff"
```

---

#### GET /api/v1/cot/summary

Top movers (largest weekly speculator net change) and positioning extremes.

**Tags:** `cot`

```bash
curl http://localhost:8000/api/v1/cot/summary
```

```json
{
  "top_movers": [
    {"market": "Euro Fx", "symbol": "099741", "change_spec_net": 12500, "report": "tff"}
  ],
  "extremes": [
    {"market": "Gold", "symbol": "088691", "long_pct": 82.3, "short_pct": 17.7, "report": "tff"}
  ]
}
```

---

### Macro

#### GET /api/v1/macro

Full macro panel: Dollar Smile, VIX regime, conflicts, prices, calendar.

**Tags:** `macro`

Prefers the DB snapshot; falls back to `data/macro/latest.json`.

```bash
curl http://localhost:8000/api/v1/macro
```

Returns a dynamic JSON object with keys like `date`, `cot_date`, `prices`, `vix_regime`, `dollar_smile`, `trading_levels`, `calendar`.

---

#### GET /api/v1/macro/indicators

Subset of key macro indicators: HYG, TIP, TNX, IRX, Copper, EEM.

**Tags:** `macro`

```bash
curl http://localhost:8000/api/v1/macro/indicators
```

```json
{
  "HYG": {"price": 76.5, "chg1d": -0.3, "chg5d": -0.8},
  "TIP": {"price": 109.2, "chg1d": 0.1, "chg5d": 0.5}
}
```

---

### Backtests

#### GET /api/v1/backtests/summary

Aggregate backtest performance statistics.

**Tags:** `backtests`

```bash
curl http://localhost:8000/api/v1/backtests/summary
```

```json
{
  "total_trades": 50,
  "wins": 32,
  "losses": 18,
  "win_rate": 64.0,
  "avg_pnl_rr": 1.35,
  "avg_duration_hours": 48.5
}
```

---

#### GET /api/v1/backtests/trades

Individual backtest trade results, ordered by entry date descending.

**Tags:** `backtests`

**Query Parameters:**

| Parameter    | Type   | Default | Description                       |
|-------------|--------|---------|-----------------------------------|
| `instrument` | string | null    | Filter by instrument key          |
| `limit`      | int    | 50      | Max results (1-500)               |

```bash
curl "http://localhost:8000/api/v1/backtests/trades?instrument=EURUSD&limit=10"
```

```json
[
  {
    "id": 1,
    "instrument": "EURUSD",
    "direction": "bull",
    "grade": "A",
    "score": 9,
    "entry_date": "2026-03-20T10:00:00",
    "entry_price": 1.085,
    "exit_date": "2026-03-22T14:30:00",
    "exit_price": 1.095,
    "exit_reason": "t1_hit",
    "pnl_pips": 100,
    "pnl_rr": 1.67,
    "duration_hours": 52.5
  }
]
```

---

### Webhook

#### POST /api/v1/webhook/push-alert

Receive a batch of signals from the analysis pipeline (v1 compatibility).

**Tags:** `webhook`

**Request Body (JSON):**

| Field       | Type              | Required | Description                                  |
|-------------|-------------------|----------|----------------------------------------------|
| `signals`   | `array[object]`   | No       | List of signal dicts from the pipeline       |
| `generated` | `string`          | No       | ISO timestamp when the batch was generated   |

```bash
curl -X POST http://localhost:8000/api/v1/webhook/push-alert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <key>" \
  -d '{
    "signals": [
      {
        "instrument": "EURUSD",
        "direction": "bull",
        "grade": "A",
        "score": 10,
        "entry_price": 1.0850,
        "stop_loss": 1.0790,
        "target_1": 1.0950,
        "target_2": 1.1020
      }
    ],
    "generated": "2026-03-26T08:00:00+00:00"
  }'
```

```json
{
  "status": "ok",
  "received": 1
}
```

---

## Middleware Stack

Requests pass through middleware in this order:

1. **CORS** -- Restricted to configured origins (`CORS_ORIGINS` env var)
2. **RateLimitMiddleware** -- Per-IP sliding window (60 req/min default)
3. **APIKeyMiddleware** -- `X-API-Key` header on `/api/v1/*` when `SCALP_API_KEY` is set

---

## Interactive Docs

FastAPI auto-generates rich interactive documentation from the Pydantic response models:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
