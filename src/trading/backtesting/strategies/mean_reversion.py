"""
Mean Reversion at Key Levels Strategy.

Entry rules:
  LONG:  Price at demand zone AND RSI < 30 (oversold)
  SHORT: Price at supply zone AND RSI > 70 (overbought)

Uses PWH/PWL/PDH/PDL approximations as additional key levels.
Quick exit: mean reversion target is SMA20.
Stop loss: Beyond the zone + ATR buffer.

Position sizing: 1% risk per trade.
"""

from typing import Dict, List
from ..engine import Strategy, Bar, Portfolio, Indicators


class MeanReversionStrategy(Strategy):
    """Mean reversion strategy at supply/demand zones with RSI confirmation."""

    name = "Mean Reversion"

    def __init__(
        self,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        rsi_period: int = 14,
        sma_exit_period: int = 20,
        atr_period: int = 14,
        pivot_length: int = 10,
        zone_atr_buffer: float = 0.25,
        sl_buffer_atr: float = 0.3,
        risk_pct: float = 0.01,
        max_positions: int = 6,
        max_hold_bars: int = 8,
    ):
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.rsi_period = rsi_period
        self.sma_exit_period = sma_exit_period
        self.atr_period = atr_period
        self.pivot_length = pivot_length
        self.zone_atr_buffer = zone_atr_buffer
        self.sl_buffer_atr = sl_buffer_atr
        self.risk_pct = risk_pct
        self.max_positions = max_positions
        self.max_hold_bars = max_hold_bars

    def _find_pivot_highs(self, bars: List[Bar], length: int) -> List[tuple]:
        pivots = []
        for i in range(length, len(bars) - length):
            window = [bars[j].high for j in range(i - length, i + length + 1)]
            if bars[i].high == max(window):
                pivots.append((i, bars[i].high))
        return pivots

    def _find_pivot_lows(self, bars: List[Bar], length: int) -> List[tuple]:
        pivots = []
        for i in range(length, len(bars) - length):
            window = [bars[j].low for j in range(i - length, i + length + 1)]
            if bars[i].low == min(window):
                pivots.append((i, bars[i].low))
        return pivots

    def _build_zones(self, bars: List[Bar], atr: float):
        """Build supply and demand zones. Returns (supply_zones, demand_zones)."""
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

        for idx, val in ph[-15:]:
            top = val
            bottom = val - atr_buf
            poi = (top + bottom) / 2
            if not overlapping(poi, supply_zones):
                supply_zones.append({
                    "top": top, "bottom": bottom, "poi": poi,
                    "idx": idx, "status": "intact",
                })

        for idx, val in pl[-15:]:
            bottom = val
            top = val + atr_buf
            poi = (top + bottom) / 2
            if not overlapping(poi, demand_zones):
                demand_zones.append({
                    "top": top, "bottom": bottom, "poi": poi,
                    "idx": idx, "status": "intact",
                })

        # Check for broken zones
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

        supply_zones = [z for z in supply_zones if z["status"] == "intact"]
        demand_zones = [z for z in demand_zones if z["status"] == "intact"]

        return supply_zones, demand_zones

    def _get_weekly_levels(self, bars: List[Bar]):
        """Approximate PDH/PDL/PWH/PWL from weekly bars.
        PDH/PDL = previous bar high/low.
        PWH/PWL = high/low of bars[-8:-1] (roughly previous week's range in weekly data).
        """
        pdh = pdl = pwh = pwl = None

        if len(bars) >= 2:
            pdh = bars[-2].high
            pdl = bars[-2].low

        if len(bars) >= 8:
            week_bars = bars[-8:-1]
            pwh = max(b.high for b in week_bars)
            pwl = min(b.low for b in week_bars)

        return pdh, pdl, pwh, pwl

    def on_bar(
        self,
        date: str,
        bars_by_instrument: Dict[str, List[Bar]],
        portfolio: Portfolio,
        engine,
    ) -> List[Dict]:
        actions = []
        ind = Indicators()

        # First, check for time-based exits on open trades
        for trade_id in list(portfolio.open_trades.keys()):
            trade = portfolio.open_trades[trade_id]
            bars = bars_by_instrument.get(trade.instrument, [])
            if not bars:
                continue

            price = bars[-1].close
            sma20 = ind.sma(bars, self.sma_exit_period)

            # Exit conditions for mean reversion:
            # 1. Price has reverted to SMA20
            # 2. Max holding period exceeded
            should_exit = False
            reason = ""

            if trade.bars_held >= self.max_hold_bars:
                should_exit = True
                reason = f"max_hold_period ({self.max_hold_bars} bars)"

            elif sma20 is not None:
                if trade.direction == "long" and price >= sma20:
                    should_exit = True
                    reason = f"mean_reversion_target SMA{self.sma_exit_period}={sma20:.4f}"
                elif trade.direction == "short" and price <= sma20:
                    should_exit = True
                    reason = f"mean_reversion_target SMA{self.sma_exit_period}={sma20:.4f}"

            if should_exit:
                actions.append({
                    "action": "close",
                    "trade_id": trade_id,
                    "reason": reason,
                })

        open_instruments = {t.instrument for t in portfolio.open_trades.values()}

        for instrument, bars in bars_by_instrument.items():
            min_bars = max(self.pivot_length * 2 + 5, self.atr_period + 1, self.rsi_period + 1, self.sma_exit_period + 1)
            if len(bars) < min_bars:
                continue

            if instrument in open_instruments:
                continue
            if len(portfolio.open_trades) >= self.max_positions:
                break

            price = bars[-1].close
            atr = ind.atr(bars, self.atr_period)
            rsi = ind.rsi(bars, self.rsi_period)

            if not atr or atr <= 0 or rsi is None:
                continue

            supply_zones, demand_zones = self._build_zones(bars, atr)
            pdh, pdl, pwh, pwl = self._get_weekly_levels(bars)

            # LONG: RSI oversold + at demand zone or key support
            if rsi < self.rsi_oversold:
                at_demand = False
                zone_bottom = None

                # Check demand zones
                for zone in demand_zones:
                    if zone["bottom"] <= price <= zone["top"]:
                        at_demand = True
                        zone_bottom = zone["bottom"]
                        break

                # Check key levels as additional demand
                if not at_demand:
                    for level in [pdl, pwl]:
                        if level and abs(price - level) <= atr * 0.3:
                            at_demand = True
                            zone_bottom = level - atr * self.zone_atr_buffer
                            break

                if at_demand and zone_bottom is not None:
                    sl = zone_bottom - atr * self.sl_buffer_atr
                    sma20 = ind.sma(bars, self.sma_exit_period)
                    # Target is SMA20 (mean reversion)
                    tp = sma20 if sma20 and sma20 > price else price + atr * 2

                    size = portfolio.position_size_from_risk(self.risk_pct, price, sl)
                    if size > 0:
                        actions.append({
                            "action": "open",
                            "instrument": instrument,
                            "direction": "long",
                            "entry_price": price,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "size": size,
                            "use_risk_sizing": False,
                            "reason": f"mean_reversion long RSI={rsi:.1f} at demand/support",
                        })

            # SHORT: RSI overbought + at supply zone or key resistance
            elif rsi > self.rsi_overbought:
                at_supply = False
                zone_top = None

                for zone in supply_zones:
                    if zone["bottom"] <= price <= zone["top"]:
                        at_supply = True
                        zone_top = zone["top"]
                        break

                if not at_supply:
                    for level in [pdh, pwh]:
                        if level and abs(price - level) <= atr * 0.3:
                            at_supply = True
                            zone_top = level + atr * self.zone_atr_buffer
                            break

                if at_supply and zone_top is not None:
                    sl = zone_top + atr * self.sl_buffer_atr
                    sma20 = ind.sma(bars, self.sma_exit_period)
                    tp = sma20 if sma20 and sma20 < price else price - atr * 2

                    size = portfolio.position_size_from_risk(self.risk_pct, price, sl)
                    if size > 0:
                        actions.append({
                            "action": "open",
                            "instrument": instrument,
                            "direction": "short",
                            "entry_price": price,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "size": size,
                            "use_risk_sizing": False,
                            "reason": f"mean_reversion short RSI={rsi:.1f} at supply/resistance",
                        })

        return actions
