---
name: financial-analysis
description: Background skill providing COT position analysis, instrument correlation, and backtesting metric context for trading-related code changes.
user-invocable: false
---

# Financial Analysis Context

This skill provides domain knowledge for trading-related code. It is NOT user-invocable — it runs as background context.

## COT Position Analysis
- Net positions = Long - Short (commercials are hedgers, non-commercials are speculators)
- Extreme readings: z-score > 2.0 or < -2.0 vs 3-year lookback
- Commercials vs Non-Commercials divergence = potential reversal signal
- Open Interest trend confirms position conviction

## Instrument Correlation Metrics
- Gold/Silver ratio: normal 60-80, elevated = risk-off
- DXY inverse correlation with Gold and EUR/USD
- VIX/SPX inverse correlation: VIX spike = SPX drop
- Copper/Gold ratio: proxy for global growth expectations
- Oil/CAD and Oil/NOK: commodity currency correlation

## Backtesting Metrics
- **Sharpe Ratio**: (Return - RiskFree) / StdDev. Good > 1.0, Great > 2.0
- **Sortino Ratio**: Like Sharpe but only penalizes downside volatility
- **Max Drawdown**: Largest peak-to-trough decline. Acceptable < 20%
- **Win Rate**: % of profitable trades. Context-dependent (high R:R can profit at 30%)
- **Risk:Reward (R:R)**: TP distance / SL distance. Minimum 1.5:1 for trend following
- **Expectancy**: (WinRate x AvgWin) - (LossRate x AvgLoss). Must be positive.
- **Profit Factor**: Gross Profit / Gross Loss. Good > 1.5

## Session Times (CET)
- Asia: 00:00-09:00
- London: 08:00-17:00
- New York: 14:30-21:00
- Overlap (London/NY): 14:30-17:00 (highest volume)
