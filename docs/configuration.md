# Configuration Reference

All configuration lives in three places: `config/*.yaml` files, `.env` environment variables, and `pyproject.toml` for build/test settings.

## Environment Variables (.env)

Copy `.env.example` to `.env`. All keys are optional -- the system runs fully on free public data without them.

| Variable              | Default                          | Purpose                                      |
|-----------------------|----------------------------------|----------------------------------------------|
| `TWELVEDATA_API_KEY`  | (none)                           | Premium price data (800 req/day free tier)    |
| `FINNHUB_API_KEY`     | (none)                           | Alternative price/quote data (60 req/min free)|
| `FRED_API_KEY`        | (none)                           | FRED macro data (higher rate limits)          |
| `TELEGRAM_TOKEN`      | (none)                           | Telegram bot token for signal alerts          |
| `TELEGRAM_CHAT_ID`    | (none)                           | Telegram chat to send alerts to               |
| `DISCORD_WEBHOOK`     | (none)                           | Discord webhook URL for signal alerts         |
| `SCALP_API_KEY`       | (none)                           | API authentication key (empty = public mode)  |
| `CORS_ORIGINS`        | `http://localhost:3000`          | Comma-separated allowed CORS origins          |
| `DATABASE_URL`        | `sqlite:///data/cot-explorer.db` | SQLAlchemy database URL                       |
| `RATE_LIMIT_PER_MINUTE` | `60`                           | Max API requests per IP per minute            |

### Authentication behavior

- If `SCALP_API_KEY` is empty or unset: all `/api/v1/*` routes are public.
- If set: clients must send `X-API-Key: <value>` header on all `/api/v1/*` requests. Non-API routes (health, docs) remain public.

### CORS

`CORS_ORIGINS` accepts a comma-separated list:

```bash
CORS_ORIGINS=http://localhost:3000,https://cot.example.com
```

## instruments.yaml

Path: `config/instruments.yaml`

Defines the 12 tracked instruments plus 6 macro indicator symbols.

### Instrument fields

| Field              | Type    | Required | Description                                       |
|--------------------|---------|----------|---------------------------------------------------|
| `key`              | string  | Yes      | Unique identifier (e.g. `EURUSD`, `Gold`)         |
| `name`             | string  | Yes      | Display name (e.g. `EUR/USD`, `Gull`)             |
| `symbol`           | string  | Yes      | Yahoo Finance ticker                              |
| `label`            | string  | Yes      | Category label for UI grouping                    |
| `category`         | string  | Yes      | `valuta`, `ravarer`, or `aksjer`                  |
| `class`            | string  | Yes      | Priority class: `A` (forex), `B` (commodities), `C` (equities) |
| `session`          | string  | Yes      | Preferred trading session in CET                  |
| `cot_market`       | string  | Nullable | CFTC market name for COT data lookup              |
| `stooq`            | string  | Nullable | Stooq.com symbol for free price data              |
| `twelvedata`       | string  | Nullable | Twelvedata API symbol                             |
| `finnhub`          | string  | Nullable | Finnhub API symbol                                |
| `news_risk_on_dir` | string  | Nullable | Direction during risk-on sentiment (`bull`/`bear`) |
| `news_risk_off_dir`| string  | Nullable | Direction during risk-off sentiment                |

### Current instruments

| Key     | Category  | Class | COT Market                  |
|---------|-----------|-------|-----------------------------|
| EURUSD  | valuta    | A     | euro fx                     |
| USDJPY  | valuta    | A     | japanese yen                |
| GBPUSD  | valuta    | A     | british pound               |
| AUDUSD  | valuta    | A     | (none)                      |
| DXY     | valuta    | A     | usd index                   |
| Gold    | ravarer   | B     | gold                        |
| Silver  | ravarer   | B     | silver                      |
| Brent   | ravarer   | B     | crude oil, light sweet      |
| WTI     | ravarer   | B     | crude oil, light sweet      |
| SPX     | aksjer    | C     | s&p 500 consolidated        |
| NAS100  | aksjer    | C     | nasdaq mini                 |
| VIX     | aksjer    | C     | (none)                      |

### Macro symbols

The `macro_symbols` section maps macro indicator tickers used for Dollar Smile, yield curve, and intermarket analysis:

| Key    | Symbol  | Purpose                        |
|--------|---------|--------------------------------|
| HYG    | HYG     | High Yield Corp Bond ETF       |
| TIP    | TIP     | TIPS Bond ETF                  |
| TNX    | ^TNX    | 10-year Treasury yield         |
| IRX    | ^IRX    | 3-month Treasury bill          |
| Copper | HG=F    | Copper futures (growth proxy)  |
| EEM    | EEM     | Emerging Markets ETF           |

## scoring.yaml

Path: `config/scoring.yaml`

Defines the 12-point confluence scoring system, grade thresholds, timeframe classification, and VIX regime sizing.

### Scoring criteria (12 points total)

Each criterion is a boolean check worth 1 point:

| ID                  | Description                                            |
|---------------------|--------------------------------------------------------|
| `sma200`            | Price above 200-day SMA (D1 trend)                     |
| `momentum_20d`      | 20-day price change confirms direction                 |
| `cot_confirms`      | CFTC speculator positioning confirms direction         |
| `cot_strong`        | Speculator net > 10% of open interest                  |
| `at_level_now`      | Price within ATR tolerance of a structure level        |
| `htf_level_nearby`  | Nearest level has D1/Weekly weight (>= 3)              |
| `trend_congruent`   | D1 and 4H EMA9 trends align                           |
| `no_event_risk`     | No high-impact events within 4 hours                   |
| `news_confirms`     | RSS news sentiment confirms direction                  |
| `fund_confirms`     | FRED macro indicators confirm direction                |
| `bos_confirms`      | Break of Structure on 1H/4H confirms                   |
| `smc_struct_confirms` | 1H SMC market structure confirms                     |

### Grade thresholds

| Grade | Min Score | Meaning          |
|-------|-----------|------------------|
| A+    | 11        | Very high conviction |
| A     | 9         | High conviction  |
| B     | 6         | Moderate         |
| C     | 0         | Low / watchlist  |

### Timeframe bias

| Bias      | Min Score | Required Criteria              | Holding Period  |
|-----------|-----------|--------------------------------|-----------------|
| MAKRO     | 6         | cot_confirms, htf_level_nearby | Days to weeks   |
| SWING     | 4         | htf_level_nearby               | Hours to days   |
| SCALP     | 2         | at_level_now (session required)| Minutes         |
| WATCHLIST | 0         | (none)                         | Not ready       |

### VIX regime position sizing

| Regime   | Max VIX | Size Label | Factor |
|----------|---------|------------|--------|
| normal   | 20      | Full       | 1.0    |
| elevated | 30      | Halv       | 0.5    |
| extreme  | 999     | Kvart      | 0.25   |

### Level weight hierarchy

| Weight | Level Type                         |
|--------|------------------------------------|
| 5      | PWH/PWL (Previous Week High/Low)   |
| 4      | PDH/PDL (Previous Day High/Low)    |
| 3      | D1 swing / PDC / SMC 1H zones     |
| 2      | 4H swing / SMC 4H zones           |
| 1      | 15m pivot / SMC 15m zones          |

### At-level tolerances (x ATR 15m)

| Level Weight | Tolerance |
|--------------|-----------|
| 1            | 0.30      |
| 2            | 0.35      |
| 3+           | 0.45      |

Level merge distance: `0.5 x ATR`

## Data Sources

All data sources are legal and free-tier:

| Source       | Data Type      | Rate Limit      | Key Required |
|--------------|----------------|-----------------|--------------|
| CFTC.gov     | COT reports    | Public domain   | No           |
| FRED         | Macro data     | 120 req/min     | Optional     |
| Yahoo Finance| Daily prices   | Personal use    | No           |
| Stooq        | Daily prices   | Free, no key    | No           |
| Twelvedata   | Intraday prices| 800 req/day     | Yes (free)   |
| Finnhub      | Quotes         | 60 req/min      | Yes (free)   |

## pyproject.toml

Build and development tool configuration:

- **Python**: >= 3.11 required
- **Linter**: Ruff (line length 120, target py311)
- **Tests**: pytest with asyncio auto mode, `tests/` directory
- **Type checker**: mypy (py311, strict warnings)
