# Trading Strategy Guide -- Cot-ExplorerV2

Last updated: 2026-03-25

This guide explains the trading strategies, scoring system, risk management, and data sources used by Cot-ExplorerV2.

---

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [The 12-Point Confluence Scoring System](#the-12-point-confluence-scoring-system)
3. [Smart Money Concepts (SMC)](#smart-money-concepts-smc)
4. [Risk Management Rules](#risk-management-rules)
5. [Data Sources and Update Frequencies](#data-sources-and-update-frequencies)
6. [Running Backtests](#running-backtests)
7. [Interpreting Backtest Results](#interpreting-backtest-results)

---

## Strategy Overview

Cot-ExplorerV2 generates trading signals across 12 instruments (4 FX pairs, 4 commodities, 3 indices, 1 volatility index) using four complementary analysis layers:

### Strategy 1: COT Momentum

**Source:** CFTC Commitments of Traders reports (4 types: TFF, Legacy, Disaggregated, Supplemental)

**Logic:** Institutional positioning flow reveals where the "smart money" is placing bets. The strategy classifies each market's speculator net position as LONG (>4% of OI), SHORT (<-4% of OI), or NEUTRAL. It also tracks momentum -- whether speculators are adding to positions (OKER/increasing), reversing (SNUR/turning), or holding steady (STABIL/stable).

**Signal Criteria:**
- COT confirms direction: speculator positioning aligns with the proposed trade direction
- COT strong positioning: speculator net exceeds 10% of total open interest -- a high-conviction signal
- COT momentum is increasing (OKER), not reversing

**Timeframe:** Weekly data, released every Friday at 15:30 ET. Best suited for MAKRO (hold days/weeks) and SWING (hold hours/days) trades.

### Strategy 2: SMC Confluence

**Source:** Price action analysis ported from FluidTrades SMC Lite Pine Script

**Logic:** Smart Money Concepts identify where institutional order flow creates tradeable structure. The engine computes swing structure (HH/LH/HL/LL), supply/demand zones, break of structure (BOS), and multi-timeframe alignment across 15m, 1H, and 4H timeframes.

**Signal Criteria:**
- BOS on 1H/4H confirms trade direction
- SMC 1H market structure (HH+HL for bullish, LH+LL for bearish) confirms direction
- Price is at or near an intact supply/demand zone (point of interest)
- D1 + 4H trend alignment

**Timeframe:** Intraday to multi-day. All timeframes benefit from SMC structure.

### Strategy 3: Macro Regime

**Source:** FRED economic data (GDP, CPI, NFP, Claims, JOLTS), CNN Fear & Greed Index, RSS news sentiment, macro indicators (HYG, TIP, TNX, IRX, Copper, EEM)

**Logic:** The macro regime determines the background environment for trading. The Dollar Smile model classifies USD behavior based on VIX levels, HY spreads, and yield curve shape. Fundamental scoring uses an EdgeFinder-style weighted category consensus.

**Signal Criteria:**
- Fundamental indicators confirm trade direction
- News sentiment (risk-on/risk-off) confirms direction
- No high-impact economic events within 4 hours
- VIX regime determines position sizing (Normal/Elevated/Extreme)

**Timeframe:** Daily macro environment. Updates 4x daily during market hours.

### Strategy 4: Mean Reversion (Level-to-Level)

**Source:** Multi-weight price level system combining PDH/PDL, PWH/PWL, D1 swings, 4H swings, 15m pivots, and SMC zones

**Logic:** The setup builder constructs level-to-level (L2L) trade setups where entry, stop loss, and targets are all tied to structural price levels rather than arbitrary ATR multiples. Entry is at a support/demand zone (long) or resistance/supply zone (short). Stop loss is placed at structure (zone boundary + buffer), not mechanical distance.

**Signal Criteria:**
- Price is at a high-timeframe level (weight >= 3 for D1/Weekly)
- A level exists nearby (within ATR tolerance)
- Target 1 provides minimum 1.5:1 reward-to-risk based on actual structural distance
- Entry is within maximum distance from current price (scaled by level weight)

**Timeframe:** D1/4H for MAKRO setups. 1H/15m for SCALP setups.

---

## The 12-Point Confluence Scoring System

Every instrument is scored on 12 binary criteria. Each criterion is worth 1 point (0 or 1), for a maximum score of 12. The scoring is defined in `config/scoring.yaml`.

### Criteria Breakdown

| # | ID | Label | Description |
|---|---|---|---|
| 1 | `sma200` | Over SMA200 (D1 trend) | Price is above the 200-day simple moving average |
| 2 | `momentum_20d` | Momentum 20d confirms | 20-day price change confirms the proposed direction |
| 3 | `cot_confirms` | COT confirms direction | CFTC speculator positioning aligns with direction |
| 4 | `cot_strong` | COT strong positioning (>10%) | Speculator net > 10% of total open interest |
| 5 | `at_level_now` | Price AT HTF level now | Price is within tight ATR tolerance of a structure level |
| 6 | `htf_level_nearby` | HTF level D1/Weekly | Nearest level has D1/Weekly weight (>= 3) |
| 7 | `trend_congruent` | D1 + 4H trend aligned | Daily and 4-hour EMA9 trends are congruent |
| 8 | `no_event_risk` | No event risk (4h) | No high-impact economic events within 4 hours |
| 9 | `news_confirms` | News sentiment confirms | RSS news sentiment (risk-on/risk-off) aligns with direction |
| 10 | `fund_confirms` | Fundamental confirms | FRED macro indicators confirm direction |
| 11 | `bos_confirms` | BOS 1H/4H confirms direction | Break of Structure on 1H/4H confirms direction |
| 12 | `smc_struct_confirms` | SMC 1H structure confirms | 1H SMC market structure (HH/HL or LH/LL) confirms direction |

### Grading Scale

| Grade | Min Score | Meaning |
|---|---|---|
| A+ | 11 | Exceptional confluence. High conviction. |
| A | 9 | Strong confluence. Tradeable with full size. |
| B | 6 | Moderate confluence. Tradeable with reduced size. |
| C | < 6 | Weak confluence. Watchlist only. |

### Timeframe Bias Classification

The system classifies each signal into a timeframe category based on score and specific criteria:

| Timeframe | Min Score | Required Criteria | Hold Period |
|---|---|---|---|
| MAKRO | 6 | `cot_confirms` AND `htf_level_nearby` | Days to weeks |
| SWING | 4 | `htf_level_nearby` | Hours to days |
| SCALP | 2 | `at_level_now` (+ active session) | Minutes |
| WATCHLIST | 0 | None | Not ready |

### VIX Regime Position Sizing

The VIX level determines position size scaling:

| Regime | VIX Range | Position Size | Scale Factor |
|---|---|---|---|
| Normal | VIX <= 20 | Full | 1.0x |
| Elevated | 20 < VIX <= 30 | Half | 0.5x |
| Extreme | VIX > 30 | Quarter | 0.25x |

---

## Smart Money Concepts (SMC)

The SMC engine (`smc.py` / `src/analysis/smc.py`) is a Python port of the FluidTrades SMC Lite Pine Script indicator. It provides institutional-grade structure analysis.

### Core Concepts

#### Swing Structure (HH/LH/HL/LL)

The engine identifies pivot highs and pivot lows using a configurable lookback window (default: 10 bars). Each pivot is classified relative to the previous pivot:

- **HH (Higher High):** Current pivot high is above the previous pivot high -- bullish continuation
- **LH (Lower High):** Current pivot high is below the previous pivot high -- bearish pressure
- **HL (Higher Low):** Current pivot low is above the previous pivot low -- bullish support
- **LL (Lower Low):** Current pivot low is below the previous pivot low -- bearish continuation

**Market Structure Classification:**
- BULLISH: Last swing high = HH AND last swing low = HL
- BEARISH: Last swing high = LH AND last swing low = LL
- BULLISH_SVAK (weak bullish): Last swing high = HH but low is not HL
- BEARISH_SVAK (weak bearish): Last swing low = LL but high is not LH
- MIXED: Neither bullish nor bearish pattern

#### Supply and Demand Zones

Zones are constructed around pivot points:

- **Supply Zone (above price):** Created at pivot highs. Top = pivot high value. Bottom = high minus ATR buffer (ATR * box_width / 10). These are areas where institutional selling is expected.
- **Demand Zone (below price):** Created at pivot lows. Bottom = pivot low value. Top = low plus ATR buffer. These are areas where institutional buying is expected.

Overlap filtering prevents redundant zones: a new zone is only created if its POI (point of interest = midpoint) is more than 2x ATR from any existing zone.

#### Break of Structure (BOS)

BOS occurs when price closes through a supply or demand zone:

- **BOS Up (BOS_opp):** Close >= supply zone top. The zone is marked "bos_brutt" (broken). Bullish signal.
- **BOS Down (BOS_ned):** Close <= demand zone bottom. Bearish signal.

BOS levels become future support/resistance and inform the `bos_confirms` scoring criterion.

#### Change of Character (CHoCH)

A CHoCH is identified when the overall structure shifts -- for example, from a series of HH/HL (bullish) to the first LH/LL (bearish). This is implicitly captured by the `determine_structure()` function transitioning between BULLISH and BEARISH states.

### Swing Labels

The system processes swing labels across multiple timeframes:

- **15m:** Intraday pivots with `n=3` (3 bars each side). Weight = 1.
- **4H:** Aggregated from 1H bars via `to_4h()`. Swing levels with `n=5`. Weight = 2.
- **D1:** Daily OHLC. Swing levels with `n=5`. Weight = 3.
- **Weekly:** Approximated from last 7 trading days. PWH/PWL weight = 5 (strongest).

### Level Weight Hierarchy

| Weight | Source | Significance |
|---|---|---|
| 5 | PWH/PWL (Previous Week High/Low) | Strongest -- institutional reference |
| 4 | PDH/PDL (Previous Day High/Low) | Strong -- daily pivots |
| 3 | D1 swing / PDC / SMC 1H zones | Moderate -- daily structure |
| 2 | 4H swing / SMC 4H zones | Moderate -- session structure |
| 1 | 15m pivot / SMC 15m zones | Weakest -- intraday noise |

### `is_at_level` Tolerances

Price proximity to a level is measured in multiples of 15m ATR, with wider tolerance for higher-weight levels:

| Level Weight | ATR Multiplier |
|---|---|
| Weight 1 (15m) | 0.30x ATR |
| Weight 2 (4H) | 0.35x ATR |
| Weight 3+ (D1/Weekly) | 0.45x ATR |

---

## Risk Management Rules

### Position Sizing

**Core Rule:** Risk 1% of account equity per trade.

Position size is calculated as:
```
Position Size = (Account Equity * 0.01) / (Entry - Stop Loss)
```

This is further scaled by the VIX regime factor (1.0x normal, 0.5x elevated, 0.25x extreme).

### Stop Loss Placement

Stop losses are placed at **structural levels**, never at arbitrary ATR distances from current price:

**For SMC demand/supply zones:**
- Long SL = zone bottom - 0.15x ATR(D1) buffer
- Short SL = zone top + 0.15x ATR(D1) buffer

**For line levels (PDH/PDL, D1 swing, PWH/PWL):**
- Long SL = level - (0.3x to 0.5x) ATR(D1), scaled by level weight
  - Weight >= 4: 0.5x ATR(D1)
  - Weight < 4: 0.3x ATR(D1)
- Short SL follows the same logic above the level

### Target Selection

**T1 (Target 1):** The highest-weight level beyond the entry that provides minimum 1.5:1 R:R based on actual risk distance. Higher-weight levels are preferred over closer, lower-weight levels.

**T2 (Target 2):** The next level beyond T1, or T1 + 1x risk if no further level exists.

### Entry Filters

A setup is only generated if:
1. Entry level is within maximum distance from current price (scaled by level weight)
2. T1 provides minimum 1.5:1 R:R
3. Risk (entry to SL distance) is positive and reasonable
4. ATR values are positive (sufficient market data)

### Event Risk Management

Criterion #8 (`no_event_risk`) checks for high-impact economic events within 4 hours using the ForexFactory calendar. When high-impact events are imminent:
- New positions should not be opened
- Existing positions should have stops tightened or be closed
- The criterion fails (scores 0), reducing the overall confluence score

---

## Data Sources and Update Frequencies

| Source | Data Type | Update Frequency | Rate Limit | API Key |
|---|---|---|---|---|
| CFTC.gov | COT reports (TFF, Legacy, Disaggregated, Supplemental) | Weekly (Friday 15:30 ET) | Unlimited | No |
| FRED | GDP, CPI, NFP, rates (DGS10, DTB3) | Daily (varies by series) | 120 req/min | Yes (free) |
| Yahoo Finance | OHLC, quotes (v8 API) | Real-time during market hours | Unofficial (no formal limit) | No |
| Stooq | Daily OHLC CSV | Daily after market close | Unlimited | No |
| Twelvedata | OHLC, forex | Intraday (15m/1H/4H) | 800 req/day (free) | Yes (free) |
| Finnhub | Real-time quotes | Real-time | 60 req/min (free) | Yes (free) |
| Alpha Vantage | OHLC, forex | Daily/intraday | 25 req/day (free) | Yes (free) |
| CNN | Fear & Greed Index | Hourly | Unofficial | No |
| ForexFactory | Economic calendar | Daily (scraped) | Unofficial | No |
| Google News RSS | News headlines | Every pipeline run | Unofficial | No |
| BBC News RSS | News headlines | Every pipeline run | Unofficial | No |

### Price Source Priority (Waterfall)

The system attempts data sources in priority order, falling back on failure:

1. **Twelvedata** -- highest quality, but limited to 800 requests/day
2. **Stooq** -- reliable daily CSV data, no rate limits
3. **Yahoo Finance** -- broad coverage, unofficial API
4. **Finnhub** -- real-time overlay for quotes

### Pipeline Schedule

The GitHub Actions pipeline runs 4x daily on weekdays:
- 07:45 CET (pre-London open)
- 12:30 CET (London session)
- 14:15 CET (NY overlap)
- 17:15 CET (late NY session)

---

## Running Backtests

### Prerequisites

```bash
# Install the project
pip install -e ".[dev]"

# Ensure data exists (run the pipeline at least once)
python src/trading/core/fetch_cot.py
python src/trading/core/fetch_all.py
```

### Running the Full Backtest

```bash
# Via the backtest runner module
python -m src.backtest.runner

# Or via GitHub Actions (weekly on Sunday 03:00 UTC)
# The backtest workflow restores the SQLite cache and runs automatically
```

### Backtest Configuration

The backtest uses the same scoring and setup logic as the live pipeline:
- Confluence scoring from `src/analysis/scoring.py`
- Level detection from `src/analysis/levels.py`
- SMC analysis from `src/analysis/smc.py`
- Setup construction from `src/analysis/setup_builder.py`

### Signal Outcome Tracking

The competitor analyzer (`src/competitor/analyzer.py`) tracks signal outcomes:

```python
from src.competitor.analyzer import check_signal_outcome, compute_accuracy

# Check a signal against price data
outcome = check_signal_outcome(signal_dict, price_bars)
# Returns: "t1_hit", "t2_hit", "stopped_out", "expired", or "pending"

# Compute rolling accuracy stats
stats = compute_accuracy(days=90)
# Returns: total, wins, losses, pending, expired, win_rate, avg_rr
```

---

## Interpreting Backtest Results

### Key Metrics

| Metric | Good | Acceptable | Poor |
|---|---|---|---|
| Win Rate | > 55% | 40-55% | < 40% |
| Average R:R (winners) | > 2.0 | 1.5-2.0 | < 1.5 |
| Expectancy per trade | > 0.3R | 0.1-0.3R | < 0.1R |
| Max consecutive losses | < 5 | 5-8 | > 8 |
| Sharpe Ratio | > 1.5 | 1.0-1.5 | < 1.0 |

### Grade Performance Analysis

Backtest results should be filtered by grade to validate the scoring system:

- **A+ signals (11-12/12):** Should have the highest win rate and best R:R. If not, the scoring criteria need recalibration.
- **A signals (9-10/12):** Strong performance expected. Should outperform B-grade signals.
- **B signals (6-8/12):** Moderate performance. Acceptable with smaller size.
- **C signals (<6/12):** Should be avoided. If C-grade signals perform well, the scoring system may be too conservative.

### Timeframe Validation

- **MAKRO signals:** Should have the best R:R (larger targets) but lower frequency. Average hold time: days to weeks.
- **SWING signals:** Balanced win rate and R:R. Average hold time: hours to days.
- **SCALP signals:** Highest frequency, lowest R:R. Should still be net positive after transaction costs.

### Signal Outcome Categories

| Outcome | Description | Interpretation |
|---|---|---|
| `t1_hit` | Price reached Target 1 | Win -- minimum expected outcome |
| `t2_hit` | Price reached Target 2 | Extended win -- optimal outcome |
| `stopped_out` | Price hit stop loss | Loss -- acceptable if within risk budget |
| `expired` | Neither target nor stop hit within timeframe | Neutral -- review if entry criteria were met |
| `pending` | Insufficient post-signal data | Awaiting resolution |

### Conflict Detection

The `detect_conflict()` function identifies macro-level divergences that warrant caution:

- VIX > 25 but DXY falling (risk-off without USD demand)
- Extreme fear but USD weakening (abnormal)
- Greed but VIX elevated (divergence)
- COT long USD but price falling (positioning divergence)
- HY spreads widening but VIX low (hidden credit risk)
- Inverted yield curve (recession risk)
- News sentiment vs. macro indicators divergence

When conflicts are detected, reduce conviction and position size regardless of the confluence score.
