# Pine Script v6 Library — COT Explorer

TradingView indicators, strategies, and combo scripts for the COT Explorer trading system.
All scripts are Pine Script v6 (`//@version=6`), validated by `scripts/validate_pine.py`.

## Installation on TradingView

1. Open TradingView and go to your chart.
2. Click **Pine Editor** at the bottom of the screen.
3. Click **Open > New blank indicator script** (or **New blank strategy** for strategies).
4. Copy the entire contents of the `.pine` file into the editor.
5. Click **Add to chart** (Ctrl+Enter).
6. Adjust settings via the gear icon on the indicator title bar.

### Free Account Setup (3 indicator slots)

TradingView free accounts allow 3 indicators per chart. Recommended combo layout:

| Slot | Script | Type |
|------|--------|------|
| 1 | `combos/cot_explorer_overlay.pine` | Overlay (SMC zones + L2L levels + VIX background + PDH/PDL/PWH/PWL) |
| 2 | `combos/cot_explorer_score.pine` | Pane (Confluence score histogram + COT net position) |
| 3 | `combos/cot_explorer_macro.pine` | Overlay (Macro dashboard table + Dollar Smile label) |

The combo scripts merge multiple indicators into one to stay within the 3-slot limit.

---

## Indicators (7 files)

### confluence_score.pine
12-point confluence scoring system. 7 criteria auto-calculated from price data (SMA200, momentum, HTF levels, trend alignment, BOS, SMC structure), 5 manual inputs from the Python analysis (COT, news, fundamentals). Grades: A+ (>=11), A (>=9), B (>=6), C (<6). Displayed as a histogram with a criteria table.

### cot_overlay.pine
CFTC COT data overlay using TradingView's built-in `COT:LEGACY` symbols. Shows speculator and commercial net positions, percentile ranking (52-week), momentum classification (OKER/SNUR/STABIL), and extreme position background highlights (>90th / <10th percentile). Supports EUR, JPY, GBP, Gold, Silver, Oil, SPX, Nasdaq, DXY.

### dollar_smile.pine
Dollar Smile framework indicator. Classifies the USD regime into three states: VENSTRE (risk-off, strong USD), MIDTEN (Goldilocks, weak USD), HOYRE (growth, moderate USD). Composite USD strength score (-1 to +1) from VIX (50%), DXY momentum (30%), and HY credit stress (20%).

### l2l_levels.pine
Level-to-Level (L2L) setup overlay. Manual entry/SL/T1/T2 price inputs from the Python analysis, auto-detected PDH/PDL and PWH/PWL lines. Draws entry, stop loss, and target lines with R:R calculation and a risk zone fill box. Designed for pre-trade setup visualization.

### macro_dashboard.pine
Macro regime dashboard table overlay. Fetches VIX, DXY, 10Y/3M yields, HYG, TIP, Copper, EEM. Displays values, 5-day changes, yield curve status (normal/inverted), HY credit stress, and Dollar Smile position. All data from TradingView's free-tier `request.security()`.

### smc_zones.pine
Smart Money Concepts (SMC) supply/demand zone overlay. Auto-detects pivot highs/lows, draws supply (red) and demand (green) zone boxes, removes broken zones, draws BOS lines on zone breaks. Swing classification (HH/LH/HL/LL) with structure label (BULLISH/BEARISH/MIXED).

### vix_regime.pine
VIX regime background overlay. Colors the chart background based on VIX level: red (extreme >=30), yellow (elevated >=25), light yellow (>=20), clear (normal). Shows position sizing recommendation (FULL/HALF/QUARTER) in an info table.

---

## Strategies (2 files)

### cot_reversal.pine
Backtestable COT reversal strategy. Entry when speculator positioning flips from an extreme percentile (>90th or <10th) with consecutive weeks of reversal. Optional SMA200 trend filter. ATR-based stop loss and configurable R:R take profit. Supports all major CFTC codes.

### smc_confluence.pine
Backtestable SMC + Confluence strategy. Enters when the confluence score meets a minimum threshold AND price is in a demand zone (long) or supply zone (short). Stop loss at zone boundary + ATR buffer. Combines SMC structure analysis with the 12-point scoring system.

---

## Combos (3 files)

These merge multiple indicators into single scripts for TradingView's free-tier 3-slot limit.

### cot_explorer_overlay.pine (Slot 1, overlay=true)
Combines: VIX regime background + PDH/PDL/PWH/PWL lines + SMC supply/demand zones + L2L setup lines. All modules togglable via input groups.

### cot_explorer_score.pine (Slot 2, overlay=false)
Combines: Confluence score histogram + COT net position (normalized). Shows score thresholds (A+/A/B), COT extremes, and a detailed info table with both auto and manual criteria counts.

### cot_explorer_macro.pine (Slot 3, overlay=true)
Combines: Macro dashboard table + Dollar Smile label + VIX regime background + USD strength score. Full macro regime analysis in one indicator slot.

---

## Validation

Run the validation script to check all Pine files:

```bash
python scripts/validate_pine.py
```

Checks performed:
1. `//@version=6` header present
2. `indicator()` or `strategy()` declaration found
3. Balanced brackets/parentheses
4. No deprecated Pine v4 `study()` calls

Results are written to `src/pine/VALIDATION.md`.

---

## CFTC Codes Reference

| Instrument | Code | TradingView Symbol |
|-----------|------|--------------------|
| EUR/USD | 099741 | `COT:LEGACY:099741:NC:L` |
| USD/JPY | 096742 | `COT:LEGACY:096742:NC:L` |
| GBP/USD | 092741 | `COT:LEGACY:092741:NC:L` |
| Gold | 088691 | `COT:LEGACY:088691:NC:L` |
| Silver | 084691 | `COT:LEGACY:084691:NC:L` |
| WTI Crude | 067651 | `COT:LEGACY:067651:NC:L` |
| S&P 500 | 13874A | `COT:LEGACY:13874A:NC:L` |
| Nasdaq | 209742 | `COT:LEGACY:209742:NC:L` |
| DXY | 098662 | `COT:LEGACY:098662:NC:L` |
