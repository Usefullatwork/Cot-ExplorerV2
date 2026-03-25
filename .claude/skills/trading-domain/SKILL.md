---
name: trading-domain
description: Trading domain knowledge for Cot-ExplorerV2 — scoring criteria, SMC concepts, COT analysis, Norwegian terminology
user-invocable: false
---

# Trading Domain — Cot-ExplorerV2

## 12-Point Confluence Scoring

| # | Criterion | Norwegian Label | Weight |
|---|-----------|----------------|--------|
| 1 | Price above SMA200 (D1 trend) | Over SMA200 (D1 trend) | 1 |
| 2 | 20-day momentum confirms | Momentum 20d bekrefter | 1 |
| 3 | COT confirms direction | COT bekrefter retning | 1 |
| 4 | COT strong positioning (>10%) | COT sterk posisjonering (>10%) | 1 |
| 5 | Price at HTF level now | Pris VED HTF-nivå nå | 1 |
| 6 | HTF level D1/Weekly nearby | HTF-nivå D1/Ukentlig | 1 |
| 7 | D1 + 4H trend congruent | D1 + 4H trend kongruent | 1 |
| 8 | No event risk (4h) | Ingen event-risiko (4t) | 1 |
| 9 | News sentiment confirms | Nyhetssentiment bekrefter | 1 |
| 10 | Fundamental confirms | Fundamental bekrefter | 1 |
| 11 | BOS 1H/4H confirms direction | BOS 1H/4H bekrefter retning | 1 |
| 12 | SMC 1H structure confirms | SMC 1H struktur bekrefter | 1 |

**Grades**: A+ (>=11), A (>=9), B (>=6), C (<6)
**Grade colors**: bull (>=11), warn (>=9), bear (<9)

## Timeframe Bias (cascading priority)
1. **MAKRO**: score>=6 AND cot_confirms AND htf_level_nearby — days/weeks
2. **SWING**: score>=4 AND htf_level_nearby — hours/days
3. **SCALP**: score>=2 AND at_level_now — minutes
4. **WATCHLIST**: fallback

## Level Weight Scale
| Weight | Source | ATR Tolerance |
|--------|--------|---------------|
| 5 | PWH/PWL (Previous Week) | 0.45x ATR |
| 4 | PDH/PDL (Previous Day) | 0.45x ATR |
| 3 | D1 swing / PDC | 0.45x ATR |
| 2 | 4H swing / SMC zone | 0.35x ATR |
| 1 | 15m pivot (weakest) | 0.30x ATR |

## SMC (Smart Money Concepts)
- **Structure**: BULLISH (HH+HL), BEARISH (LH+LL), BULLISH_SVAK, BEARISH_SVAK, MIXED
- **Supply Zone**: at pivot high, zone = [high - atr_buffer, high]
- **Demand Zone**: at pivot low, zone = [low, low + atr_buffer]
- **BOS** (Break of Structure): close crosses through zone -> zone marked "bos_brutt"
- **Overlap filter**: no zone within 2x ATR of existing zone

## COT Analysis
- **Bias**: LONG (pct > 4%), SHORT (pct < -4%), NØYTRAL (else). pct = spec_net / oi * 100
- **Momentum**: ØKER (adding to direction), SNUR (reversing), STABIL (no change)

## 12 Tracked Instruments
- Forex: EURUSD, USDJPY, GBPUSD, AUDUSD, DXY
- Commodities: Gold, Silver, Brent, WTI, Copper
- Equities: SPX, NAS100, VIX

## Norwegian Terminology
| Norwegian | English |
|-----------|---------|
| Støtte | Support |
| Motstand | Resistance |
| aktiv | active (at level) |
| watchlist | watchlist (not at level) |
| struktur | structure (SL type) |
| zone | zone (SL type) |
| bekrefter | confirms |
| Ingen | None/No |
| retning | direction |
| Ukentlig | Weekly |
