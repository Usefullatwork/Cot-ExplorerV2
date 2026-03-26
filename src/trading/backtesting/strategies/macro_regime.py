"""
Macro Regime Strategy.

Classifies the market into regimes and allocates accordingly:

Risk-On regime (VIX < 20, DXY weakening):
  - Long risk assets (equities, AUD, commodities)
  - Reduced USD exposure

Risk-Off regime (VIX > 25, DXY strengthening):
  - Short risk assets or flat
  - Long USD/safe havens (gold)

Neutral regime (between thresholds):
  - Reduced position sizes
  - Only highest-conviction trades

Uses fundamentals_score (COT positioning strength) for sector rotation.
Monthly rebalancing: closes all positions on first bar of new month,
then re-enters based on current regime.
"""

from typing import Dict, List, Optional
from ..engine import Strategy
from ..models import Bar, Portfolio
from ..indicators import Indicators


# Asset classification for regime-based allocation
RISK_ON_ASSETS = {"spx", "nas100", "audusd", "brent", "wti", "copper", "silver"}
RISK_OFF_ASSETS = {"gold", "usdjpy", "dxy"}
RISK_NEUTRAL_ASSETS = {"eurusd", "gbpusd"}

# Asset universe with expected direction in risk-on
ASSET_REGIME_DIR = {
    "spx": "long",       # equities rise in risk-on
    "nas100": "long",
    "eurusd": "long",    # weak USD = EUR/USD up
    "gbpusd": "long",
    "audusd": "long",    # risk currency
    "usdjpy": "long",    # risk-on = weak JPY = USD/JPY up
    "gold": "short",     # gold falls in risk-on (typically)
    "silver": "long",    # silver is industrial + precious
    "brent": "long",
    "wti": "long",
    "dxy": "short",      # weak USD in risk-on
}


class MacroRegimeStrategy(Strategy):
    """Regime-based macro allocation strategy with monthly rebalancing."""

    name = "Macro Regime"

    def __init__(
        self,
        vix_risk_on: float = 20.0,
        vix_risk_off: float = 25.0,
        dxy_instrument: str = "dxy",
        vix_instrument: str = "spx",  # VIX proxy from SPX volatility
        dxy_lookback: int = 5,
        atr_period: int = 14,
        sl_atr_mult: float = 3.0,
        risk_pct: float = 0.01,
        max_positions: int = 8,
        rebalance_bars: int = 4,  # rebalance every 4 weeks (~monthly)
    ):
        self.vix_risk_on = vix_risk_on
        self.vix_risk_off = vix_risk_off
        self.dxy_instrument = dxy_instrument
        self.vix_instrument = vix_instrument
        self.dxy_lookback = dxy_lookback
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.risk_pct = risk_pct
        self.max_positions = max_positions
        self.rebalance_bars = rebalance_bars

        self._bar_count = 0
        self._last_rebalance_month = ""

    def _estimate_vix(self, bars: List[Bar], period: int = 20) -> float:
        """Estimate VIX-like volatility from price data.
        Uses annualized standard deviation of weekly returns as a proxy.
        Returns value on ~VIX scale (0-100).
        """
        if len(bars) < period + 1:
            return 20.0  # default neutral

        returns = []
        for i in range(-period, 0):
            prev = bars[i - 1].close
            curr = bars[i].close
            if prev > 0:
                returns.append(curr / prev - 1)

        if not returns:
            return 20.0

        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        weekly_std = variance ** 0.5

        # Annualize: weekly std * sqrt(52) * 100
        annualized_vol = weekly_std * (52 ** 0.5) * 100
        return annualized_vol

    def _dxy_trend(self, bars: List[Bar], lookback: int) -> str:
        """Determine DXY trend over lookback period. Returns 'strengthening', 'weakening', or 'flat'."""
        if len(bars) < lookback + 1:
            return "flat"
        chg = bars[-1].close / bars[-(lookback + 1)].close - 1
        if chg > 0.005:
            return "strengthening"
        elif chg < -0.005:
            return "weakening"
        return "flat"

    def _classify_regime(
        self, vix_est: float, dxy_trend: str
    ) -> str:
        """Classify macro regime."""
        if vix_est < self.vix_risk_on and dxy_trend in ("weakening", "flat"):
            return "risk_on"
        elif vix_est > self.vix_risk_off and dxy_trend in ("strengthening", "flat"):
            return "risk_off"
        elif vix_est > self.vix_risk_off:
            return "risk_off"
        elif vix_est < self.vix_risk_on:
            return "risk_on"
        return "neutral"

    def _cot_strength(self, bars: List[Bar]) -> float:
        """COT positioning strength as a score from -1 to +1."""
        current = bars[-1]
        if current.spec_net is None or current.open_interest is None:
            return 0.0
        if current.open_interest == 0:
            return 0.0
        pct = current.spec_net / current.open_interest
        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, pct * 10))

    def _should_rebalance(self, date: str) -> bool:
        """Check if we should rebalance on this bar."""
        current_month = date[:7]
        if current_month != self._last_rebalance_month:
            self._last_rebalance_month = current_month
            return True
        return False

    def on_bar(
        self,
        date: str,
        bars_by_instrument: Dict[str, List[Bar]],
        portfolio: Portfolio,
        engine,
    ) -> List[Dict]:
        actions = []
        ind = Indicators()
        self._bar_count += 1

        # Only rebalance monthly
        if not self._should_rebalance(date):
            return actions

        # Estimate VIX from the most volatile equity instrument
        vix_est = 20.0
        for vix_proxy in ["spx", "nas100"]:
            if vix_proxy in bars_by_instrument:
                vix_est = self._estimate_vix(bars_by_instrument[vix_proxy], 20)
                break

        # DXY trend
        dxy_trend = "flat"
        if self.dxy_instrument in bars_by_instrument:
            dxy_bars = bars_by_instrument[self.dxy_instrument]
            if len(dxy_bars) > self.dxy_lookback:
                dxy_trend = self._dxy_trend(dxy_bars, self.dxy_lookback)

        regime = self._classify_regime(vix_est, dxy_trend)

        # Close all existing positions before rebalancing
        for trade_id in list(portfolio.open_trades.keys()):
            trade = portfolio.open_trades[trade_id]
            actions.append({
                "action": "close",
                "trade_id": trade_id,
                "reason": f"monthly_rebalance regime={regime}",
            })

        # Size factor based on regime
        if regime == "risk_on":
            size_mult = 1.0
        elif regime == "risk_off":
            size_mult = 0.5
        else:
            size_mult = 0.25

        # Score instruments by COT strength and select best
        scored = []
        for instrument, bars in bars_by_instrument.items():
            if len(bars) < max(self.atr_period + 1, 21):
                continue

            atr = ind.atr(bars, self.atr_period)
            if not atr or atr <= 0:
                continue

            cot_score = self._cot_strength(bars)
            price = bars[-1].close

            # Determine ideal direction based on regime
            asset_dir = ASSET_REGIME_DIR.get(instrument)
            if asset_dir is None:
                continue

            if regime == "risk_on":
                direction = asset_dir
            elif regime == "risk_off":
                # Flip direction for risk assets, keep for havens
                if instrument in RISK_OFF_ASSETS:
                    direction = asset_dir
                elif instrument in RISK_ON_ASSETS:
                    direction = "short" if asset_dir == "long" else "long"
                else:
                    continue  # skip neutral assets in risk-off
            else:
                # Neutral: only trade if COT strongly confirms
                if abs(cot_score) < 0.3:
                    continue
                direction = "long" if cot_score > 0 else "short"

            # COT must at least not contradict
            if direction == "long" and cot_score < -0.5:
                continue
            if direction == "short" and cot_score > 0.5:
                continue

            # Rank by absolute COT strength
            scored.append({
                "instrument": instrument,
                "direction": direction,
                "cot_score": abs(cot_score),
                "price": price,
                "atr": atr,
            })

        # Sort by COT strength descending, take top N
        scored.sort(key=lambda x: x["cot_score"], reverse=True)

        for entry in scored[:self.max_positions]:
            price = entry["price"]
            atr = entry["atr"]
            direction = entry["direction"]

            if direction == "long":
                sl = price - self.sl_atr_mult * atr
                tp = price + self.sl_atr_mult * atr * 1.5
            else:
                sl = price + self.sl_atr_mult * atr
                tp = price - self.sl_atr_mult * atr * 1.5

            size = portfolio.position_size_from_risk(
                self.risk_pct * size_mult, price, sl
            )
            if size <= 0:
                continue

            actions.append({
                "action": "open",
                "instrument": entry["instrument"],
                "direction": direction,
                "entry_price": price,
                "stop_loss": sl,
                "take_profit": tp,
                "size": size,
                "use_risk_sizing": False,
                "reason": f"macro regime={regime} dxy={dxy_trend} vix_est={vix_est:.1f} cot={entry['cot_score']:.2f}",
            })

        return actions
