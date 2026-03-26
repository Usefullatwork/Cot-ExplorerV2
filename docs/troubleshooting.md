# Troubleshooting Guide

## API Key Issues

### "Invalid or missing API key" (HTTP 401)

**Cause:** `SCALP_API_KEY` is set in `.env` but the request is missing the `X-API-Key` header.

**Fix:** Either add the header to your requests:

```bash
curl -H "X-API-Key: your-key-here" http://localhost:8000/api/v1/signals
```

Or disable authentication by removing/emptying `SCALP_API_KEY` in `.env`:

```bash
SCALP_API_KEY=
```

### FRED data not loading

**Symptoms:** Fundamentals stage logs "FEIL" or returns empty data.

**Cause:** FRED API has a default public key with low rate limits.

**Fix:**
1. Register for a free key at https://fred.stlouisfed.org/docs/api/api_key.html
2. Set `FRED_API_KEY=your-key` in `.env`

The system works without a FRED key but falls back to cached data.

### Twelvedata "Too Many Requests"

**Symptoms:** Intraday price fetches return 429 errors.

**Cause:** Free tier allows 800 API calls per day, 8 per minute.

**Fix:** The built-in `RateLimiter` (token bucket at 8 req/min) handles this automatically. If you still hit limits:
- Reduce the number of instruments configured with `twelvedata` symbols
- Wait for the daily quota to reset (midnight UTC)
- Upgrade to a paid Twelvedata plan

### Finnhub rate limits

**Symptoms:** Price fetches intermittently fail with HTTP 429.

**Cause:** Free tier is 60 requests per minute.

**Fix:** The rate limiter handles this. If exceeded:
- Reduce instruments with `finnhub` symbols
- The system falls back to Stooq/Yahoo data automatically

## CORS Errors

### "Access-Control-Allow-Origin" blocked

**Symptoms:** Browser console shows CORS errors when the frontend calls the API.

**Fix:** Add your frontend origin to `CORS_ORIGINS` in `.env`:

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://your-domain.com
```

Restart the API server after changing this value.

## Rate Limiting

### "Rate limit exceeded" (HTTP 429)

**Cause:** More than 60 requests per minute from the same IP.

**Fix:**
- For legitimate high-traffic use: increase the limit in `.env`:
  ```bash
  RATE_LIMIT_PER_MINUTE=120
  ```
- For development: the limit is per-IP, so different clients won't interfere.
- Behind a proxy: ensure `X-Forwarded-For` is set so the middleware sees real IPs instead of the proxy IP.

## Data Freshness

### COT data is stale

**Symptoms:** COT dates are more than 7 days old.

**Cause:** CFTC publishes weekly reports on Fridays (for Tuesday positions). If the pipeline hasn't run recently, data goes stale.

**Fix:**
1. Run manually: `python fetch_cot.py`
2. Check cron is active: `crontab -l`
3. Check `update.sh` logs: `tail -50 ~/cot-explorer/logs/update.log`

### Prices not updating

**Symptoms:** Price data timestamps are old.

**Fix:**
1. Run `python fetch_prices.py` manually
2. Check provider availability -- Yahoo/Stooq can have intermittent downtime
3. The system tries providers in order: Yahoo -> Stooq -> Twelvedata -> Finnhub

### Pipeline shows stage errors

Run the pipeline with verbose logging:

```bash
python -m src.pipeline.runner
```

The pipeline runs all 8 stages independently -- a failure in one stage does not block others. Check the results dict at the end:

```
[OK]   calendar: ok
[FAIL] cot: error: HTTPError(...)
[OK]   combine: ok
...
```

## Database Issues

### "database is locked"

**Cause:** Multiple writers competing on SQLite.

**Fix:**
- WAL mode is enabled by default (handles most cases)
- Ensure only one pipeline instance runs at a time
- For heavy concurrent access, consider PostgreSQL:
  ```bash
  DATABASE_URL=postgresql://user:pass@localhost/cotexplorer
  ```

### Tables missing

**Cause:** Database file exists but schema is outdated.

**Fix:**
```bash
# Recreate all tables
python -c "from src.db.engine import init_db; init_db()"

# Or run Alembic migrations
alembic upgrade head
```

### Corrupt database

```bash
# Back up the existing file
cp data/cot-explorer.db data/cot-explorer.db.bak

# Delete and recreate
rm data/cot-explorer.db
python -c "from src.db.engine import init_db; init_db()"

# Re-fetch data
python fetch_cot.py && python fetch_all.py
```

## Debugging Tips

### Enable verbose logging

```bash
# Set log level via environment
LOG_LEVEL=DEBUG python -m src.pipeline.runner
```

### Inspect the database directly

```bash
sqlite3 data/cot-explorer.db

# Check table row counts
SELECT 'instruments', COUNT(*) FROM instruments
UNION ALL SELECT 'signals', COUNT(*) FROM signals
UNION ALL SELECT 'prices_daily', COUNT(*) FROM prices_daily
UNION ALL SELECT 'cot_positions', COUNT(*) FROM cot_positions;

# Latest signal per instrument
SELECT instrument, direction, grade, score, generated_at
FROM signals
GROUP BY instrument
HAVING generated_at = MAX(generated_at);
```

### Test individual components

```bash
# Test COT fetch only
python fetch_cot.py

# Test price router
python -c "
from src.data.price_router import PriceRouter
router = PriceRouter()
print(router.fetch('EURUSD'))
"

# Test scoring
python -c "
from src.analysis.scoring import calculate_confluence
# ... pass instrument data
"
```

### Check API health

```bash
# Health endpoint (no auth required)
curl http://localhost:8000/api/v1/health

# List instruments
curl http://localhost:8000/api/v1/instruments

# Latest signals
curl http://localhost:8000/api/v1/signals
```

### Run tests

```bash
# Full suite
python -m pytest tests/ -v

# Specific module
python -m pytest tests/test_scoring.py -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: src` | Running from wrong directory | `cd` to project root |
| `sqlalchemy.exc.OperationalError: no such table` | DB not initialized | Run `init_db()` |
| `ConnectionError: CFTC` | CFTC.gov down or network issue | Retry later; cached data still works |
| `JSONDecodeError` | Corrupt data file in `data/` | Delete the file and re-fetch |
| `ValueError: invalid symbol` | Input validation rejected a symbol | Use valid instrument keys from `instruments.yaml` |
