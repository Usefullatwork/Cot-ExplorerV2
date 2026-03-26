"""
SMC + Confluence Strategy.

Uses Smart Money Concepts (supply/demand zones) combined with a
multi-factor confluence score to filter entries.

Entry rules:
  LONG:  Price at demand zone AND confluence_score >= +6/12
  SHORT: Price at supply zone AND confluence_score <= -6/12

The 12-point confluence scoring system mirrors fetch_all.py:
  1. Price > SMA200 (trend)
  2. 20-day momentum confirms direction
  3. COT bias confirms direction
  4. COT strong positioning (>10% of OI)
  5. Price at key level
  6. Higher timeframe level nearby
  7. D1 + intraday trend alignment
  8. No event risk (simplified: always true in backtest)
  9. News sentiment (simplified: neutral in backtest)
  10. Fundamental confirms (simplified: COT as proxy)
  11. BOS confirms direction
  12. SMC structure confirms direction

Stop loss: Beyond the zone boundary.
Position sizing: 1% risk per trade.
"""

from typing import Dict, List, Optional

from ..engine import Strategy
from ..indicators import Indicators
from ..models import Bar, Portfolio


class SMCConfluenceStrategy(Strategy):
    """Enters at SMC supply/demand zones filtered by confluence score."""

    name = "SMC Confluence"

    def __init__(
        self,
        min_confluence: int = 6,
        sma_period: int = 200,
        atr_period: int = 14,
        pivot_length: int = 10,
        zone_atr_buffer: float = 0.25,
        sl_buffer_atr: float = 0.15,
        tp_rr: float = 2.0,
        risk_pct: float = 0.01,
        max_positions: int = 6,
    ):
        self.min_confluence = min_confluence
        self.sma_period = sma_period
        self.atr_period = atr_period
        self.pivot_length = pivot_length
        self.zone_atr_buffer = zone_atr_buffer
        self.sl_buffer_atr = sl_buffer_atr
        self.tp_rr = tp_rr
        self.risk_pct = risk_pct
        self.max_positions = max_positions

    def _find_pivot_highs(self, bars: List[Bar], length: int) -> List[tuple]:
        """Find pivot highs: (index, value)."""
        pivots = []
        for i in range(length, len(bars) - length):
            window = [bars[j].high for j in range(i - length, i + length + 1)]
            if bars[i].high == max(window):
                pivots.append((i, bars[i].high))
        return pivots

    def _find_pivot_lows(self, bars: List[Bar], length: int) -> List[tuple]:
        """Find pivot lows: (index, value)."""
        pivots = []
        for i in range(length, len(bars) - length):
            window = [bars[j].low for j in range(i - length, i + length + 1)]
            if bars[i].low == min(window):
                pivots.append((i, bars[i].low))
        return pivots

    def _build_zones(self, bars: List[Bar], atr: float):
        """Build supply and demand zones from pivots. Returns (supply_zones, demand_zones).

        Each zone: {"top": float, "bottom": float, "poi": float, "idx": int, "status": str}
        """
        ph = self._find_pivot_highs(bars, self.pivot_length)
        pl = self._find_pivot_lows(bars, self.pivot_length)

        atr_buf = atr * self.zone_atr_buffer
        atr_overlap = atr * 2

        supply_zones = []
        demand_zones = []

        def overlapping(new_poi, zones):
            for z in zones:
                if abs(new_poi - z["poi"]) <= atr_overlap:
                    return True
            return False

        # Supply zones from pivot highs (last 20)
        for idx, val in ph[-20:]:
            top = val
            bottom = val - atr_buf
            poi = (top + bottom) / 2
            if not overlapping(poi, supply_zones):
                supply_zones.append(
                    {
                        "top": top,
                        "bottom": bottom,
                        "poi": poi,
                        "idx": idx,
                        "status": "intact",
                    }
                )

        # Demand zones from pivot lows (last 20)
        for idx, val in pl[-20:]:
            bottom = val
            top = val + atr_buf
            poi = (top + bottom) / 2
            if not overlapping(poi, demand_zones):
                demand_zones.append(
                    {
                        "top": top,
                        "bottom": bottom,
                        "poi": poi,
                        "idx": idx,
                        "status": "intact",
                    }
                )

        # Check for broken zones (BOS)
        for z in supply_zones:
            for i in range(z["idx"] + 1, len(bars)):
                if bars[i].close >= z["top"]:
                    z["status"] = "broken"
                    break

        for z in demand_zones:
            for i in range(z["idx"] + 1, len(bars)):
                if bars[i].close <= z["bottom"]:
                    z["status"] = "broken"
                    break

        # Filter to intact zones only
        supply_zones = [z for z in supply_zones if z["status"] == "intact"]
        demand_zones = [z for z in demand_zones if z["status"] == "intact"]

        return supply_zones, demand_zones

    def _detect_structure(self, bars: List[Bar]) -> str:
        """Detect market structure: BULLISH, BEARISH, or MIXED."""
        ph = self._find_pivot_highs(bars, self.pivot_length)
        pl = self._find_pivot_lows(bars, self.pivot_length)

        if len(ph) < 2 or len(pl) < 2:
            return "MIXED"

        last_high = ph[-1][1]
        prev_high = ph[-2][1]
        last_low = pl[-1][1]
        prev_low = pl[-2][1]

        hh = last_high >= prev_high
        hl = last_low >= prev_low

        if hh and hl:
            return "BULLISH"
        elif not hh and not hl:
            return "BEARISH"
        return "MIXED"

    def _detect_bos_direction(self, bars: List[Bar], atr: float) -> Optional[str]:
        """Detect most recent Break of Structure direction."""
        supply, demand = self._build_zones(bars[:-5] if len(bars) > 20 else bars, atr)
        # Check last 5 bars for BOS
        for i in range(max(0, len(bars) - 5), len(bars)):
            for z in supply:
                if bars[i].close >= z["top"]:
                    return "bullish"
            for z in demand:
                if bars[i].close <= z["bottom"]:
                    return "bearish"
        return None

    def _confluence_score(self, bars: List[Bar], direction: str, atr: float, at_zone: bool) -> int:
        """Calculate 12-point confluence score (-12 to +12).

        Positive = bullish confluence, Negative = bearish confluence.
        Each factor contributes +1 (bullish) or -1 (bearish).
        """
        ind = Indicators()
        score = 0
        price = bars[-1].close

        # 1. Price vs SMA200
        sma200 = ind.sma(bars, 200)
        if sma200:
            score += 1 if price > sma200 else -1

        # 2. 20-week momentum
        if len(bars) >= 21:
            chg20 = price / bars[-21].close - 1
            score += 1 if chg20 > 0 else -1

        # 3. COT bias confirms
        current = bars[-1]
        if current.spec_net is not None and current.open_interest:
            cot_pct = (current.spec_net / current.open_interest) * 100
            if cot_pct > 4:
                score += 1
            elif cot_pct < -4:
                score -= 1

        # 4. COT strong positioning
        if current.spec_net is not None and current.open_interest:
            cot_pct = abs(current.spec_net / current.open_interest) * 100
            if cot_pct > 10:
                score += 1 if current.spec_net > 0 else -1

        # 5. Price at key level
        if at_zone:
            score += 1 if direction == "long" else -1

        # 6. HTF level nearby (use SMA200 proximity as proxy)
        if sma200:
            dist = abs(price - sma200) / (atr * 5) if atr else 999
            if dist < 1.0:
                score += 1 if price > sma200 else -1

        # 7. Trend alignment (5w vs 20w)
        if len(bars) >= 6:
            chg5 = price / bars[-6].close - 1
            chg20_val = price / bars[-21].close - 1 if len(bars) >= 21 else chg5
            if chg5 > 0 and chg20_val > 0:
                score += 1
            elif chg5 < 0 and chg20_val < 0:
                score -= 1

        # 8. No event risk (simplified: always +1 in backtest)
        score += 1 if direction == "long" else -1

        # 9. RSI confirmation
        rsi = ind.rsi(bars, 14)
        if rsi is not None:
            if rsi < 40:
                score -= 1
            elif rsi > 60:
                score += 1

        # 10. MACD confirmation
        macd = ind.macd(bars)
        if macd:
            macd_line, sig_line, hist = macd
            if hist > 0:
                score += 1
            elif hist < 0:
                score -= 1

        # 11. BOS direction
        structure = self._detect_structure(bars)
        if structure == "BULLISH":
            score += 1
        elif structure == "BEARISH":
            score -= 1

        # 12. SMC structure confirms
        if structure == "BULLISH" and direction == "long":
            score += 1
        elif structure == "BEARISH" and direction == "short":
            score += 1  # confirms short direction
        elif structure == "BULLISH" and direction == "short":
            score -= 1
        elif structure == "BEARISH" and direction == "long":
            score -= 1

        return score

    def on_bar(
        self,
        date: str,
        bars_by_instrument: Dict[str, List[Bar]],
        portfolio: Portfolio,
        engine,
    ) -> List[Dict]:
        actions = []
        ind = Indicators()

        open_instruments = {t.instrument for t in portfolio.open_trades.values()}

        for instrument, bars in bars_by_instrument.items():
            min_bars = max(self.sma_period, self.pivot_length * 2 + 5, self.atr_period + 1)
            if len(bars) < min_bars:
                continue

            if instrument in open_instruments:
                continue
            if len(portfolio.open_trades) >= self.max_positions:
                break

            atr = ind.atr(bars, self.atr_period)
            if not atr or atr <= 0:
                continue

            price = bars[-1].close
            supply_zones, demand_zones = self._build_zones(bars, atr)

            # Check if price is at a demand zone (potential long)
            for zone in demand_zones:
                if zone["bottom"] <= price <= zone["top"]:
                    confluence = self._confluence_score(bars, "long", atr, True)
                    if confluence >= self.min_confluence:
                        sl = zone["bottom"] - atr * self.sl_buffer_atr
                        risk = price - sl
                        tp = price + risk * self.tp_rr
                        size = portfolio.position_size_from_risk(self.risk_pct, price, sl)
                        if size > 0 and risk > 0:
                            actions.append(
                                {
                                    "action": "open",
                                    "instrument": instrument,
                                    "direction": "long",
                                    "entry_price": price,
                                    "stop_loss": sl,
                                    "take_profit": tp,
                                    "size": size,
                                    "use_risk_sizing": False,
                                    "reason": (
                                        f"SMC demand zone [{zone['bottom']:.4f}-{zone['top']:.4f}]"
                                        f" confluence={confluence}/12"
                                    ),
                                }
                            )
                    break  # only process nearest zone

            # Check if price is at a supply zone (potential short)
            for zone in supply_zones:
                if zone["bottom"] <= price <= zone["top"]:
                    confluence = self._confluence_score(bars, "short", atr, True)
                    if confluence <= -self.min_confluence:
                        sl = zone["top"] + atr * self.sl_buffer_atr
                        risk = sl - price
                        tp = price - risk * self.tp_rr
                        size = portfolio.position_size_from_risk(self.risk_pct, price, sl)
                        if size > 0 and risk > 0:
                            actions.append(
                                {
                                    "action": "open",
                                    "instrument": instrument,
                                    "direction": "short",
                                    "entry_price": price,
                                    "stop_loss": sl,
                                    "take_profit": tp,
                                    "size": size,
                                    "use_risk_sizing": False,
                                    "reason": (
                                        f"SMC supply zone [{zone['bottom']:.4f}-{zone['top']:.4f}]"
                                        f" confluence={confluence}/12"
                                    ),
                                }
                            )
                    break

        return actions
