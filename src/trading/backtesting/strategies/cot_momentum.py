"""
COT Momentum Strategy.

Entry rules:
  LONG:  spec_net increasing for 3+ consecutive weeks AND price > SMA200
  SHORT: spec_net decreasing for 3+ consecutive weeks AND price < SMA200

Exit rules:
  Stop loss:   2x ATR from entry
  Take profit: 3x ATR from entry

Position sizing: 1% risk per trade (based on entry-to-stop distance).

Only one position per instrument at a time.
Weekly bars (COT data is weekly).
"""

from typing import Dict, List
from ..engine import Strategy, Bar, Portfolio, Indicators


class COTMomentumStrategy(Strategy):
    """Trend-following strategy driven by COT speculator positioning momentum."""

    name = "COT Momentum"

    def __init__(
        self,
        trend_weeks: int = 3,
        sma_period: int = 200,
        atr_period: int = 14,
        sl_atr_mult: float = 2.0,
        tp_atr_mult: float = 3.0,
        risk_pct: float = 0.01,
        max_positions: int = 6,
    ):
        self.trend_weeks = trend_weeks
        self.sma_period = sma_period
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.risk_pct = risk_pct
        self.max_positions = max_positions

    def on_bar(
        self,
        date: str,
        bars_by_instrument: Dict[str, List[Bar]],
        portfolio: Portfolio,
        engine,
    ) -> List[Dict]:
        actions = []
        ind = Indicators()

        # Instruments already in open trades
        open_instruments = {t.instrument for t in portfolio.open_trades.values()}

        for instrument, bars in bars_by_instrument.items():
            if len(bars) < max(self.sma_period, self.atr_period + 1, self.trend_weeks + 2):
                continue

            current = bars[-1]

            # Skip instruments with no COT data
            if current.spec_net is None:
                continue

            # Already have a position in this instrument
            if instrument in open_instruments:
                continue

            # Max positions check
            if len(portfolio.open_trades) >= self.max_positions:
                break

            # Calculate indicators
            sma200 = ind.sma(bars, self.sma_period)
            atr = ind.atr(bars, self.atr_period)
            cot_trend = ind.spec_net_trend(bars, self.trend_weeks)

            if sma200 is None or atr is None or atr <= 0 or cot_trend is None:
                continue

            price = current.close

            # LONG signal: COT increasing + price above SMA200
            if cot_trend == "increasing" and price > sma200:
                sl = price - self.sl_atr_mult * atr
                tp = price + self.tp_atr_mult * atr
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
                        "use_risk_sizing": False,  # already calculated
                        "reason": f"COT momentum long: spec_net increasing {self.trend_weeks}w, price > SMA{self.sma_period}",
                    })

            # SHORT signal: COT decreasing + price below SMA200
            elif cot_trend == "decreasing" and price < sma200:
                sl = price + self.sl_atr_mult * atr
                tp = price - self.tp_atr_mult * atr
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
                        "reason": f"COT momentum short: spec_net decreasing {self.trend_weeks}w, price < SMA{self.sma_period}",
                    })

        return actions
