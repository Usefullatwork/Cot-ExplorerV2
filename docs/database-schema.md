# Database Schema Reference

Cot-ExplorerV2 uses SQLite via SQLAlchemy 2.0 ORM. The database file defaults to `data/cot-explorer.db` and uses WAL mode with foreign keys enabled.

All 10 tables are defined in `src/db/models.py`. CRUD operations live in `src/db/repository.py`. Migrations are managed via Alembic (`alembic/`).

## ER Diagram (Text)

```
 instruments (PK: key)
   |
   |--- 1:N ---> prices_daily (FK: instrument -> instruments.key)
   |--- 1:N ---> prices_intraday (FK: instrument -> instruments.key)
   |--- 1:N ---> signals (FK: instrument -> instruments.key)
                    |
                    |--- 1:N ---> backtest_results (FK: signal_id -> signals.id)

 cot_positions       (standalone, keyed by symbol+report_type+date)
 fundamentals        (standalone, keyed by indicator_key)
 macro_snapshots     (standalone, time-series snapshots)
 calendar_events     (standalone, economic calendar)
 audit_log           (standalone, system event log)
```

## Table Details

### 1. instruments

Primary reference table for all tracked markets.

| Column     | Type        | Nullable | Notes                        |
|------------|-------------|----------|------------------------------|
| key        | String(32)  | PK       | e.g. `EURUSD`, `Gold`, `SPX` |
| name       | String(64)  | No       | Display name                 |
| symbol     | String(32)  | No       | Yahoo Finance symbol         |
| label      | String(32)  | No       | Category label               |
| category   | String(32)  | No       | `valuta`, `ravarer`, `aksjer` |
| class      | String(8)   | No       | `A`, `B`, or `C`             |
| session    | String(64)  | No       | Trading session hours (CET)  |
| cot_market | String(64)  | Yes      | CFTC market name for COT lookup |
| active     | Boolean     | No       | Default `true`               |

**Relationships:** `prices_daily`, `prices_intraday`, `signals` (all cascade delete-orphan)

---

### 2. prices_daily

Daily OHLCV price bars per instrument.

| Column     | Type        | Nullable | Notes                   |
|------------|-------------|----------|-------------------------|
| id         | Integer     | PK, auto | -                       |
| instrument | String(32)  | No       | FK -> instruments.key   |
| date       | String(10)  | No       | Format: `YYYY-MM-DD`    |
| open       | Float       | Yes      | Opening price           |
| high       | Float       | No       | -                       |
| low        | Float       | No       | -                       |
| close      | Float       | No       | -                       |
| volume     | Float       | Yes      | -                       |
| source     | String(32)  | Yes      | Provider name           |

**Indexes:** `ix_price_daily_instrument`, `ix_price_daily_date`
**Unique constraint:** `(instrument, date)`

---

### 3. prices_intraday

Sub-daily price bars for multiple timeframes.

| Column     | Type        | Nullable | Notes                         |
|------------|-------------|----------|-------------------------------|
| id         | Integer     | PK, auto | -                             |
| instrument | String(32)  | No       | FK -> instruments.key         |
| timestamp  | DateTime    | No       | Full timestamp                |
| timeframe  | String(8)   | No       | `15m`, `1h`, `4h`            |
| high       | Float       | No       | -                             |
| low        | Float       | No       | -                             |
| close      | Float       | No       | -                             |
| source     | String(32)  | Yes      | Provider name                 |

**Indexes:** `ix_price_intraday_instrument`, `ix_price_intraday_ts`
**Unique constraint:** `(instrument, timestamp, timeframe)`

---

### 4. cot_positions

CFTC Commitments of Traders weekly reports.

| Column          | Type         | Nullable | Notes                                        |
|-----------------|--------------|----------|----------------------------------------------|
| id              | Integer      | PK, auto | -                                            |
| symbol          | String(32)   | No       | CFTC commodity code                          |
| market          | String(128)  | No       | CFTC market name                             |
| report_type     | String(32)   | No       | `tff`, `legacy`, `disaggregated`, `supplemental` |
| date            | String(10)   | No       | Report date `YYYY-MM-DD`                     |
| open_interest   | Integer      | No       | Total open interest                          |
| change_oi       | Integer      | No       | Week-over-week OI change                     |
| spec_long       | Integer      | No       | Speculator (non-commercial) longs            |
| spec_short      | Integer      | No       | Speculator shorts                            |
| spec_net        | Integer      | No       | spec_long - spec_short                       |
| comm_long       | Integer      | No       | Commercial (hedger) longs                    |
| comm_short      | Integer      | No       | Commercial shorts                            |
| comm_net        | Integer      | No       | comm_long - comm_short                       |
| nonrept_long    | Integer      | No       | Non-reportable longs                         |
| nonrept_short   | Integer      | No       | Non-reportable shorts                        |
| nonrept_net     | Integer      | No       | nonrept_long - nonrept_short                 |
| change_spec_net | Integer      | No       | Week-over-week change in spec_net            |
| category        | String(32)   | Yes      | Optional grouping                            |

**Indexes:** `ix_cot_symbol`, `ix_cot_date`, `ix_cot_report_type`
**Unique constraint:** `(symbol, report_type, date)`

---

### 5. signals

Generated trading signals with 12-point confluence scores.

| Column         | Type        | Nullable | Notes                               |
|----------------|-------------|----------|---------------------------------------|
| id             | Integer     | PK, auto | -                                     |
| instrument     | String(32)  | No       | FK -> instruments.key                 |
| generated_at   | DateTime    | No       | Default: `utcnow()`                  |
| direction      | String(8)   | No       | `bull` or `bear`                      |
| grade          | String(4)   | No       | `A+`, `A`, `B`, `C`                  |
| score          | Integer     | No       | 0-12 confluence score                 |
| timeframe_bias | String(16)  | No       | `MAKRO`, `SWING`, `SCALP`, `WATCHLIST` |
| entry_price    | Float       | Yes      | Suggested entry                       |
| stop_loss      | Float       | Yes      | Stop loss level                       |
| target_1       | Float       | Yes      | First target                          |
| target_2       | Float       | Yes      | Second target                         |
| rr_t1          | Float       | Yes      | Risk:reward to target 1               |
| rr_t2          | Float       | Yes      | Risk:reward to target 2               |
| entry_weight   | Integer     | Yes      | Level weight at entry                 |
| t1_weight      | Integer     | Yes      | Level weight at target 1              |
| sl_type        | String(16)  | Yes      | Stop loss type                        |
| at_level_now   | Boolean     | Yes      | Price at HTF level now                |
| vix_regime     | String(16)  | Yes      | `normal`, `elevated`, `extreme`       |
| pos_size       | String(16)  | Yes      | Position size label                   |
| score_details  | Text        | Yes      | JSON: per-criterion breakdown         |
| metadata       | Text        | Yes      | JSON: additional signal metadata      |

**Indexes:** `ix_signal_instrument`, `ix_signal_generated`, `ix_signal_grade`, `ix_signal_score`
**Relationships:** `backtest_results` (cascade delete-orphan)

---

### 6. backtest_results

Historical performance of signals when backtested against price data.

| Column         | Type        | Nullable | Notes                                   |
|----------------|-------------|----------|-----------------------------------------|
| id             | Integer     | PK, auto | -                                       |
| signal_id      | Integer     | No       | FK -> signals.id                        |
| instrument     | String(32)  | No       | Denormalized for fast queries           |
| entry_date     | DateTime    | No       | -                                       |
| entry_price    | Float       | No       | -                                       |
| exit_date      | DateTime    | Yes      | Null if still open                      |
| exit_price     | Float       | Yes      | -                                       |
| exit_reason    | String(32)  | Yes      | `t1_hit`, `t2_hit`, `stopped_out`, `expired` |
| pnl_pips       | Float       | Yes      | P&L in pips                             |
| pnl_rr         | Float       | Yes      | P&L in risk:reward multiples            |
| duration_hours | Float       | Yes      | Trade duration                          |
| direction      | String(8)   | No       | `bull` or `bear`                        |
| grade          | String(4)   | No       | Signal grade at entry                   |
| score          | Integer     | No       | Signal score at entry                   |

**Indexes:** `ix_backtest_instrument`, `ix_backtest_entry_date`

---

### 7. fundamentals

FRED macro economic indicators (GDP, CPI, rates, etc.).

| Column         | Type        | Nullable | Notes                       |
|----------------|-------------|----------|-----------------------------|
| id             | Integer     | PK, auto | -                           |
| updated_at     | DateTime    | No       | Default: `utcnow()`        |
| indicator_key  | String(32)  | No       | FRED series ID              |
| label          | String(128) | No       | Human-readable name         |
| current_value  | Float       | Yes      | Latest reading              |
| previous_value | Float       | Yes      | Prior reading               |
| score          | Integer     | No       | Direction score (default 0) |
| trend          | String(16)  | Yes      | Trend direction             |
| date           | String(10)  | Yes      | Reading date                |

**Indexes:** `ix_fundamental_key`, `ix_fundamental_updated`

---

### 8. macro_snapshots

Point-in-time snapshots of the full macro environment.

| Column         | Type        | Nullable | Notes                        |
|----------------|-------------|----------|------------------------------|
| id             | Integer     | PK, auto | -                            |
| generated_at   | DateTime    | No       | Default: `utcnow()`         |
| vix_price      | Float       | Yes      | VIX level                   |
| vix_regime     | String(16)  | Yes      | `normal`, `elevated`, `extreme` |
| dollar_smile   | String(16)  | Yes      | Dollar Smile regime          |
| usd_bias       | String(32)  | Yes      | USD directional bias         |
| fear_greed     | Float       | Yes      | Fear & Greed index value     |
| news_sentiment | Text        | Yes      | JSON: aggregated news sentiment |
| yield_curve    | Float       | Yes      | Yield curve spread           |
| conflicts      | Text        | Yes      | JSON: geopolitical conflicts |
| full_json      | Text        | Yes      | JSON: complete macro panel   |

**Indexes:** `ix_macro_generated`

---

### 9. calendar_events

Economic calendar events (FOMC, NFP, CPI releases, etc.).

| Column                | Type        | Nullable | Notes                     |
|-----------------------|-------------|----------|---------------------------|
| id                    | Integer     | PK, auto | -                         |
| date                  | DateTime    | No       | Event date/time           |
| title                 | String(256) | No       | Event description         |
| country               | String(8)   | No       | ISO country code          |
| impact                | String(16)  | No       | `low`, `medium`, `high`   |
| forecast              | String(32)  | Yes      | Consensus forecast        |
| previous              | String(32)  | Yes      | Previous reading          |
| actual                | String(32)  | Yes      | Actual result (post-event)|
| hours_away            | Float       | Yes      | Hours until event         |
| affected_instruments  | Text        | Yes      | JSON list of instrument keys |

**Indexes:** `ix_calendar_date`, `ix_calendar_impact`

---

### 10. audit_log

System audit trail for pipeline runs, errors, and security events.

| Column     | Type        | Nullable | Notes                     |
|------------|-------------|----------|---------------------------|
| id         | Integer     | PK, auto | -                         |
| timestamp  | DateTime    | No       | Default: `utcnow()`      |
| event_type | String(64)  | No       | e.g. `pipeline_start`    |
| details    | Text        | Yes      | JSON: event-specific data |

**Indexes:** `ix_audit_timestamp`, `ix_audit_event_type`

## Database Configuration

SQLite WAL mode and foreign keys are enabled automatically on every connection via the `_enable_wal` listener in `src/db/engine.py`.

```python
# Override database location via env var or direct parameter
DATABASE_URL=sqlite:///path/to/my.db

# Or programmatically
from src.db.engine import init_db
init_db("sqlite:///custom/path.db")
```

## Migrations

Schema migrations use Alembic. Config is in `alembic.ini`.

```bash
# Create a new migration after modifying models.py
alembic revision --autogenerate -m "description"

# Apply pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```
