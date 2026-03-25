---
name: testing-patterns
description: Pytest conventions, fixture patterns, and assertion helpers for Cot-ExplorerV2
user-invocable: false
---

# Testing Patterns — Cot-ExplorerV2

## Project Test Structure

```
tests/
  conftest.py           # DB engine, session, app_client fixtures
  fixtures/
    price_data.py       # make_daily_rows(), make_15m_rows(), etc.
    cot_data.py         # make_cot_data(), COT_MAP, SAMPLE_COT_DB
    tagged_levels.py    # make_support_level(), EURUSD_SUPPORTS/RESISTANCES
  unit/                 # Pure function tests (no mocking needed)
  integration/          # API + DB tests (in-memory SQLite)
```

## Fixture Conventions

### Price Data (EURUSD-style, ~1.08xx range)
- `BASE_PRICE = 1.0850`
- `DAILY_ATR = 0.0060` (60 pips)
- `INTRADAY_ATR_15M = 0.0012` (12 pips)
- All generators use `random.Random(42)` for reproducibility

### Row Types
- `Row = tuple[float, float, float]` — (high, low, close)
- `OhlcBar` — Pydantic model with .high, .low, .close

### Norwegian Assertion Values
- COT bias: `"LONG"`, `"SHORT"`, `"NØYTRAL"` (at ±4% threshold)
- COT momentum: `"ØKER"`, `"SNUR"`, `"STABIL"`
- Setup status: `"aktiv"`, `"watchlist"`
- SMC structure: `"BULLISH"`, `"BEARISH"`, `"BULLISH_SVAK"`, `"BEARISH_SVAK"`, `"MIXED"`
- Scoring grades: `"A+"`, `"A"`, `"B"`, `"C"`
- Timeframe bias: `"MAKRO"`, `"SWING"`, `"SCALP"`, `"WATCHLIST"`

## Integration Test Patterns

### FastAPI Client
```python
from httpx import AsyncClient, ASGITransport
from src.api.app import create_app

transport = ASGITransport(app=create_app())
async with AsyncClient(transport=transport, base_url="http://test") as client:
    resp = await client.get("/health")
```

### DB Fixtures
- `db_engine`: `create_engine("sqlite:///:memory:")`
- `db_session`: sessionmaker bound to test engine
- Monkeypatch `src.db.engine.get_engine` and `src.db.engine.get_session`

## Key Boundaries
- NEVER mock analysis modules (they are pure functions)
- ONLY mock: `urllib.request.urlopen` (sentiment HTTP), `subprocess.run` (pipeline)
- Monkeypatch env vars for auth tests: `os.environ["SCALP_API_KEY"]`
