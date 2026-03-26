# Backtesting Guide

The backtesting engine tests trading strategies against historical COT + price data. It uses zero external dependencies (stdlib Python only).

Source code: `src/trading/backtesting/`

## Architecture

```
BacktestEngine
  |-- DataLoader      Loads price + COT JSON from data/
  |-- Strategy        User-defined strategy (on_bar callback)
  |-- Portfolio       Tracks positions, equity, risk sizing
  |-- Indicators      SMA, EMA, ATR, RSI, MACD, COT metrics
  |-- metrics.py      Sharpe, Sortino, max drawdown, profit factor, etc.
```

## Running a Backtest

### 1. Basic usage

```python
from src.trading.backtesting.engine import BacktestEngine, Strategy, Bar

class MyCotStrategy(Strategy):
    name = "COT Momentum"

    def on_bar(self, date, bars_by_instrument, portfolio, engine):
        actions = []
        for inst, bars in bars_by_instrument.items():
            if len(bars) < 5:
                continue

            current = bars[-1]
            prev = bars[-2]

            # Go long when spec_net is increasing
            if (current.spec_net is not None
                and prev.spec_net is not None
                and current.spec_net > prev.spec_net
                and inst not in [t.instrument for t in portfolio.open_trades.values()]):

                actions.append({
                    "action": "open",
                    "instrument": inst,
                    "direction": "long",
                    "entry_price": current.close,
                    "stop_loss": current.close * 0.98,
                    "take_profit": current.close * 1.04,
                    "reason": "COT spec_net increasing",
                })

        return actions

# Run the backtest
engine = BacktestEngine(
    strategy=MyCotStrategy(),
    data_dir="data",
    instruments=["eurusd", "gold", "spx"],
    start_date="2020-01-01",
    end_date="2024-12-31",
    initial_capital=100000.0,
    risk_per_trade=0.01,
)

results = engine.run()
```

### 2. Engine parameters

| Parameter        | Default    | Description                                 |
|------------------|------------|---------------------------------------------|
| `strategy`       | (required) | Strategy instance with `on_bar` method      |
| `data_dir`       | (required) | Path to data directory                      |
| `instruments`    | `None`     | List of instrument keys (None = all available) |
| `start_date`     | `None`     | Start date filter `YYYY-MM-DD`              |
| `end_date`       | `None`     | End date filter `YYYY-MM-DD`                |
| `initial_capital` | `100000.0` | Starting capital                           |
| `risk_per_trade` | `0.01`     | Risk per trade as fraction of equity (1%)   |

## Writing a Custom Strategy

Every strategy must subclass `Strategy` and implement `on_bar()`.

### The on_bar callback

```python
def on_bar(self, date, bars_by_instrument, portfolio, engine):
    """Called once per date with all available data.

    Args:
        date: Current date string (YYYY-MM-DD)
        bars_by_instrument: {instrument: [Bar, ...]} -- full history up to current date
        portfolio: Portfolio object with open_trades, cash, equity
        engine: BacktestEngine reference (access indicators via engine.indicators)

    Returns:
        List of action dicts
    """
```

### Action format

**Open a trade:**
```python
{
    "action": "open",
    "instrument": "eurusd",
    "direction": "long",       # "long" or "short"
    "entry_price": 1.0850,
    "stop_loss": 1.0800,       # optional
    "take_profit": 1.0950,     # optional
    "size": 1.0,               # optional (auto-calculated from risk if stop_loss provided)
    "use_risk_sizing": True,   # default True, uses risk_per_trade to size position
    "reason": "COT bullish",   # optional annotation
}
```

**Close a trade:**
```python
{
    "action": "close",
    "trade_id": 42,            # from portfolio.open_trades
    "reason": "manual exit",
}
```

### Available data in Bar objects

Each `Bar` contains:

| Field          | Type  | Description                    |
|----------------|-------|--------------------------------|
| `date`         | str   | Date string                    |
| `instrument`   | str   | Instrument key                 |
| `price`/`close`| float | Closing price                  |
| `high`         | float | High price                     |
| `low`          | float | Low price                      |
| `spec_net`     | int   | COT speculator net position    |
| `spec_long`    | int   | COT speculator longs           |
| `spec_short`   | int   | COT speculator shorts          |
| `open_interest`| int   | Total open interest            |

### Using indicators

```python
def on_bar(self, date, bars_by_instrument, portfolio, engine):
    ind = engine.indicators
    actions = []

    for inst, bars in bars_by_instrument.items():
        sma200 = ind.sma(bars, 200)
        ema9 = ind.ema(bars, 9)
        atr14 = ind.atr(bars, 14)
        rsi14 = ind.rsi(bars, 14)
        macd = ind.macd(bars)  # returns (macd_line, signal_line, histogram)
        cot_change = ind.spec_net_change(bars, weeks=3)
        cot_trend = ind.spec_net_trend(bars, weeks=3)
        cot_pct = ind.cot_pct(bars[-1])  # spec_net as % of OI

        # All indicators return None if insufficient data
        if sma200 is None:
            continue

        # Your logic here...

    return actions
```

## Interpreting Results

The `engine.run()` method returns a comprehensive results dict.

### Results structure

```python
{
    "strategy": "MyCotStrategy",
    "instruments": ["eurusd", "gold", "spx"],
    "period": {
        "start": "2020-01-03",
        "end": "2024-12-27",
        "bars": 260,
    },
    "capital": {
        "initial": 100000.0,
        "final": 115432.50,
        "total_return_pct": 15.43,
    },
    "trades": {
        "total": 87,
        "winners": 52,
        "losers": 35,
        "win_rate": 59.77,
        "avg_pnl": 177.38,
        "avg_winner": 412.50,
        "avg_loser": -172.30,
        "profit_factor": 1.85,
        "expectancy": 177.38,
        "avg_bars_held": 4.2,
    },
    "risk": {
        "sharpe_ratio": 1.245,
        "sortino_ratio": 1.890,
        "max_drawdown_pct": 8.75,
        "calmar_ratio": 1.762,
        "recovery_factor": 1.76,
    },
    "equity_curve": [("2020-01-03", 100000.0), ...],
    "trade_log": [
        {
            "id": 1,
            "instrument": "eurusd",
            "direction": "long",
            "entry_price": 1.085,
            "entry_date": "2020-01-10",
            "exit_price": 1.095,
            "exit_date": "2020-01-24",
            "stop_loss": 1.080,
            "take_profit": 1.095,
            "size": 20000.0,
            "reason": "COT bullish",
            "exit_reason": "take_profit",
            "pnl": 200.0,
            "pnl_pct": 0.9217,
            "bars_held": 2,
            "is_open": false,
        },
        ...
    ],
}
```

### Key metrics explained

| Metric          | Good Value      | Description                                |
|-----------------|-----------------|--------------------------------------------|
| Win rate        | > 50%           | Percentage of profitable trades            |
| Profit factor   | > 1.5           | Gross profit / gross loss                  |
| Sharpe ratio    | > 1.0           | Risk-adjusted return (annualized, weekly)  |
| Sortino ratio   | > 1.5           | Like Sharpe but penalizes only downside    |
| Max drawdown    | < 15%           | Largest peak-to-trough decline             |
| Calmar ratio    | > 1.0           | Annualized return / max drawdown           |
| Recovery factor | > 1.0           | Net profit / max drawdown (absolute)       |
| Expectancy      | > 0             | Expected P&L per trade                     |
| Avg bars held   | varies          | Average trade duration in bars (weeks)     |

## API Endpoints

Backtest results stored in the database are accessible via the REST API.

### GET /api/v1/backtests/summary

Aggregate statistics across all stored backtest results.

```json
{
    "total_trades": 150,
    "wins": 87,
    "losses": 63,
    "win_rate": 58.0,
    "avg_pnl_rr": 0.45,
    "avg_duration_hours": 72.3
}
```

### GET /api/v1/backtests/trades

List individual backtest trades with optional filters.

| Parameter    | Type   | Default | Description                |
|-------------|--------|---------|----------------------------|
| `instrument` | string | (all)   | Filter by instrument key   |
| `limit`      | int    | 50      | Max results (1-500)        |

```bash
curl "http://localhost:8000/api/v1/backtests/trades?instrument=EURUSD&limit=20"
```

## Data Requirements

The backtest engine reads from the `data/` directory:

```
data/
  prices/
    eurusd.json          # {data: [{date, price}, ...]}
    gold.json
    spx.json
    cot_map.json         # Maps COT symbol codes to price keys
  timeseries/
    099741_tff.json      # {data: [{date, spec_net, spec_long, spec_short, oi}, ...]}
    088691_legacy.json
    ...
```

Ensure data is populated before running backtests:

```bash
python fetch_cot.py
python fetch_prices.py
python build_price_history.py
python build_timeseries.py
```

## Tips

- **Start simple.** Begin with a single-instrument, single-criterion strategy and add complexity gradually.
- **Avoid overfitting.** If a strategy has more than 5 parameters, it is likely curve-fitted to historical data.
- **COT data is weekly.** Strategies using COT positioning operate on a weekly bar frequency. Intraday strategies need price data from Twelvedata/Finnhub.
- **Check data coverage.** The `engine.load_data()` method populates `_all_bars` -- inspect its keys to see which instruments loaded successfully.
- **Position sizing.** When `stop_loss` is provided and `use_risk_sizing` is True (default), the engine auto-calculates position size so that a stop loss hit loses exactly `risk_per_trade` percent of equity.
