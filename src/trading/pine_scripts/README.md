# Pine Script Indicators for TradingView

Four custom indicators ported from the Cot-ExplorerV2 analysis engine
to Pine Script v5 for use on TradingView charts.

## Indicators

### 1. SMC Zones (`smc_zones.pine`)

**Smart Money Concepts** overlay indicator directly ported from `smc.py`.

**Features:**
- Pivot High/Low detection with configurable lookback
- Supply zones (red boxes) at pivot highs
- Demand zones (green boxes) at pivot lows
- Zone invalidation: zones disappear when price breaks through
- BOS (Break of Structure) lines with labels
- Swing classification labels: HH, HL, LH, LL
- POI (Point of Interest) dotted lines at zone midpoints
- Info table showing current structure and ATR

**Key Settings:**
- `Pivot Length` (default 10): Bars on each side to confirm a pivot. Higher values = fewer but more significant zones.
- `Zone ATR Buffer` (default 2.5): Zone thickness. Matches `box_width` parameter from `smc.py`.
- `ATR Length` (default 50): Period for ATR calculation.

**Best Used On:** 15-minute to 4-hour charts for intraday; daily for swing trading.

---

### 2. Confluence Score (`confluence_score.pine`)

**12-point scoring system** matching the `fetch_all.py` confluence logic.

**Components (each scores -1, 0, or +1):**

| # | Component | Bullish (+1) | Bearish (-1) |
|---|-----------|-------------|--------------|
| 1 | SMA200 Trend | Price above | Price below |
| 2 | SMA50 Trend | Price above | Price below |
| 3 | RSI Regime | RSI > 60 | RSI < 40 |
| 4 | MACD Signal | Histogram > 0 | Histogram < 0 |
| 5 | Volume Trend | Above-avg + bullish candle | Above-avg + bearish candle |
| 6 | ATR Regime | Low vol + bullish | Low vol + bearish |
| 7 | HTF Trend | Weekly close > SMA50 | Weekly close < SMA50 |
| 8 | Momentum | 20-bar return > 1% | 20-bar return < -1% |
| 9 | Key Level | Near demand zone | Near supply zone |
| 10 | BOS Direction | Last BOS was bullish | Last BOS was bearish |
| 11 | Zone Quality | In demand zone | In supply zone |
| 12 | EMA9 Align | Price > EMA9 | Price < EMA9 |

**Grade Scale:** A+ (>=11), A (>=9), B (>=6), C (>=3), D (>=0), F (<0)

**Alerts:** Fires when score crosses above bullish or below bearish threshold.

---

### 3. Macro Dashboard (`macro_dashboard.pine`)

**Overlay table** showing macro regime indicators in real-time.

**Displays:**
- **VIX**: Level, 5-day change, regime classification (Normal/Elevated/Extreme)
- **DXY**: Level, N-day change, trend direction
- **Yield Curve**: 10Y-2Y spread with inversion warning
- **Fear & Greed Est.**: Composite score from RSI + VIX + momentum + trend
- **Risk Regime**: Risk-On / Risk-Off / Neutral classification
- **Dollar Smile**: Left (safe haven) / Middle (Goldilocks) / Right (growth)
- **Position Sizing**: Full / Half / Quarter based on VIX

**Requirements:**
- Works on any TradingView plan (free tier included)
- Uses `request.security()` for VIX, DXY, and yield data
- Configurable symbol inputs for different data providers

---

### 4. COT Overlay (`cot_overlay.pine`)

**COT data visualization** with two input modes.

**Mode 1: Manual Input (Free Tier)**
Enter weekly speculator net positions from the CFTC report:
1. Go to [CFTC COT Reports](https://www.cftc.gov/dea/futures/deacmesf.htm)
2. Find your instrument and note the "Noncommercial" or "Leveraged Funds" net position
3. Enter the last 8 weeks of data in the indicator settings
4. Update weekly (reports are released every Friday)

**Mode 2: CFTC Auto (Premium)**
If you have TradingView Premium, the indicator can fetch CFTC data directly.
Set the CFTC symbol to the appropriate code (e.g., `CFTC:099741_F_TFF_ALL` for EUR futures).

**CFTC Symbol Codes (for Auto mode):**

| Instrument | CFTC Code | Symbol |
|-----------|-----------|--------|
| EUR/USD | 099741 | `CFTC:099741_F_TFF_ALL` |
| USD/JPY | 096742 | `CFTC:096742_F_TFF_ALL` |
| GBP/USD | 092741 | `CFTC:092741_F_TFF_ALL` |
| AUD/USD | 232741 | `CFTC:232741_F_TFF_ALL` |
| Gold | 088691 | `CFTC:088691_F_ALL` |
| Silver | 084691 | `CFTC:084691_F_ALL` |
| WTI Crude | 067651 | `CFTC:067651_F_ALL` |
| S&P 500 | 133741 | `CFTC:133741_F_ALL` |
| Nasdaq 100 | 209742 | `CFTC:209742_F_ALL` |
| USD Index | 098662 | `CFTC:098662_F_ALL` |

**Displays:**
- Net position histogram (green = increasing, red = decreasing)
- Weekly change momentum
- OI-normalized percentage line
- Trend classification (Increasing/Decreasing/Mixed over N weeks)
- Bias label (Long/Short/Neutral based on %OI thresholds)

---

## Installation

### Adding to TradingView

1. Open TradingView and navigate to your chart
2. Click the **Pine Editor** tab at the bottom of the screen
3. Click **Open** > **New blank indicator script**
4. Copy the entire contents of the `.pine` file into the editor
5. Click **Add to chart** (or press Ctrl+Enter)
6. The indicator will appear on your chart with default settings

### Recommended Setup

For the complete Cot-ExplorerV2 analysis on TradingView:

1. **Main chart**: Add `SMC Zones` as overlay
2. **Pane 1**: Add `Confluence Score` as a separate pane below price
3. **Pane 2**: Add `COT Overlay` as another pane (if using COT data)
4. **Dashboard**: Add `Macro Dashboard` as overlay (appears as a table)

### Chart Settings

- **Forex**: Use 1H or 4H timeframe with Pivot Length 5-10
- **Commodities**: Use 4H or Daily with Pivot Length 10-15
- **Indices**: Use Daily with Pivot Length 10-20

---

## Free Account Limitations

TradingView free accounts have the following limits:

| Feature | Free | Plus | Premium |
|---------|------|------|---------|
| Indicators per chart | 3 | 5 | 25 |
| `request.security()` calls | 40 | 40 | 40 |
| Custom timeframes | No | Yes | Yes |
| CFTC data access | No | No | Yes |

**Workarounds for free accounts:**

- Use only 2-3 indicators at a time
- The `Macro Dashboard` uses 4 security calls (well within limits)
- Use `Manual` mode for COT data (no Premium needed)
- Save multiple chart layouts with different indicator combinations

---

## Manual COT Data Workflow

Since TradingView free plans cannot access CFTC data directly:

1. **Friday evening**: CFTC releases the COT report for the previous Tuesday
2. **Visit**: [CFTC COT Reports](https://www.cftc.gov/dea/futures/deacmesf.htm) or [Barchart COT](https://www.barchart.com/futures/commitment-of-traders)
3. **Find** your instrument in the Traders in Financial Futures (TFF) report
4. **Note** the "Leveraged Funds" net position (Long - Short)
5. **Open** the COT Overlay settings on TradingView
6. **Shift** all values down by one week (Week 1 -> Week 2, etc.)
7. **Enter** the new value in "This Week Net"
8. **Update** Open Interest from the report

This takes about 2 minutes per instrument per week.

---

## Customization

All indicators use `input.*` functions for full customization.
Right-click the indicator name and select "Settings" to adjust:

- Colors and transparency
- Calculation periods
- Display toggles (show/hide components)
- Threshold values
- Symbol inputs for macro data
