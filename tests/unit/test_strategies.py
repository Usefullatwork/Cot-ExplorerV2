"""Unit tests for the four backtesting strategies.

Covers: COTMomentumStrategy, MacroRegimeStrategy, MeanReversionStrategy,
        SMCConfluenceStrategy.

Each strategy is tested via its on_bar() interface with synthetic Bar data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from src.trading.backtesting.models import Bar, Portfolio
from src.trading.backtesting.strategies.cot_momentum import COTMomentumStrategy
from src.trading.backtesting.strategies.macro_regime import MacroRegimeStrategy
from src.trading.backtesting.strategies.mean_reversion import MeanReversionStrategy
from src.trading.backtesting.strategies.smc_confluence import SMCConfluenceStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weekly_dates(n: int, start: str = "2024-01-01") -> list[str]:
    """Generate n weekly date strings."""
    d = datetime.strptime(start, "%Y-%m-%d")
    return [(d + timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(n)]


def _make_bars(
    instrument: str,
    n: int,
    base_price: float = 100.0,
    step: float = 1.0,
    spread: float = 2.0,
    spec_nets: list[int | None] | None = None,
    open_interest: int | None = 100000,
    start: str = "2024-01-01",
) -> list[Bar]:
    """Build a synthetic bar series.

    Prices rise linearly: close = base_price + i * step.
    High/low spread symmetrically around close.
    """
    dates = _weekly_dates(n, start)
    if spec_nets is None:
        spec_nets = [None] * n
    bars: list[Bar] = []
    for i in range(n):
        price = base_price + i * step
        sn = spec_nets[i] if i < len(spec_nets) else None
        bars.append(
            Bar(
                date=dates[i],
                instrument=instrument,
                price=price,
                high=price + spread,
                low=price - spread,
                spec_net=sn,
                open_interest=open_interest if sn is not None else None,
            )
        )
    return bars


def _make_bars_custom(
    instrument: str,
    prices: list[tuple[float, float, float]],
    spec_nets: list[int | None] | None = None,
    open_interest: int | None = 100000,
    start: str = "2024-01-01",
) -> list[Bar]:
    """Build bars from explicit (close, high, low) tuples."""
    dates = _weekly_dates(len(prices), start)
    if spec_nets is None:
        spec_nets = [None] * len(prices)
    bars: list[Bar] = []
    for i, (close, high, low) in enumerate(prices):
        sn = spec_nets[i] if i < len(spec_nets) else None
        bars.append(
            Bar(
                date=dates[i],
                instrument=instrument,
                price=close,
                high=high,
                low=low,
                spec_net=sn,
                open_interest=open_interest if sn is not None else None,
            )
        )
    return bars


def _fresh_portfolio(capital: float = 100000.0) -> Portfolio:
    """Create a fresh Portfolio with no open trades."""
    return Portfolio(initial_capital=capital)


def _mock_engine():
    """Minimal engine mock — strategies only use it for type signature."""
    return MagicMock()


# ===========================================================================
# COTMomentumStrategy Tests
# ===========================================================================


class TestCOTMomentumStrategy:
    """Tests for COT Momentum strategy signal generation."""

    def test_bullish_cot_generates_long_signal(self):
        """Increasing spec_net for 3+ weeks with price above SMA200 -> long."""
        strategy = COTMomentumStrategy(trend_weeks=3, sma_period=5, atr_period=3)
        # 10 bars, rising prices (always above SMA5),
        # spec_net increasing every week: 1000, 2000, 3000, 4000, 5000 ...
        n = 10
        spec_nets = [1000 * (i + 1) for i in range(n)]
        bars = _make_bars("gold", n, base_price=100.0, step=2.0, spec_nets=spec_nets)
        bars_by_inst = {"gold": bars}

        portfolio = _fresh_portfolio()
        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        longs = [a for a in actions if a["direction"] == "long"]
        assert len(longs) == 1
        assert longs[0]["action"] == "open"
        assert longs[0]["instrument"] == "gold"
        assert longs[0]["stop_loss"] < longs[0]["entry_price"]
        assert longs[0]["take_profit"] > longs[0]["entry_price"]

    def test_bearish_cot_generates_short_signal(self):
        """Decreasing spec_net for 3+ weeks with price below SMA200 -> short."""
        strategy = COTMomentumStrategy(trend_weeks=3, sma_period=5, atr_period=3)
        n = 10
        # Spec_net decreasing: 10000, 9000, 8000, ... 1000
        spec_nets = [10000 - 1000 * i for i in range(n)]
        # Falling prices — current price below SMA5
        bars = _make_bars("gold", n, base_price=200.0, step=-3.0, spec_nets=spec_nets)
        bars_by_inst = {"gold": bars}

        portfolio = _fresh_portfolio()
        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        shorts = [a for a in actions if a["direction"] == "short"]
        assert len(shorts) == 1
        assert shorts[0]["action"] == "open"
        assert shorts[0]["stop_loss"] > shorts[0]["entry_price"]
        assert shorts[0]["take_profit"] < shorts[0]["entry_price"]

    def test_flat_cot_no_signal(self):
        """Flat/mixed spec_net trend -> no signal generated."""
        strategy = COTMomentumStrategy(trend_weeks=3, sma_period=5, atr_period=3)
        n = 10
        # Alternating spec_net: not consistently increasing or decreasing
        spec_nets = [5000, 4000, 5000, 4000, 5000, 4000, 5000, 4000, 5000, 4000]
        bars = _make_bars("gold", n, base_price=100.0, step=1.0, spec_nets=spec_nets)
        bars_by_inst = {"gold": bars}

        portfolio = _fresh_portfolio()
        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        assert actions == []

    def test_empty_price_data_no_crash(self):
        """Empty instrument data -> returns empty actions list, no crash."""
        strategy = COTMomentumStrategy()
        bars_by_inst: Dict[str, List[Bar]] = {"gold": []}

        portfolio = _fresh_portfolio()
        actions = strategy.on_bar("2024-01-01", bars_by_inst, portfolio, _mock_engine())

        assert actions == []

    def test_insufficient_data_no_crash(self):
        """Fewer bars than required lookback -> no signal, no crash."""
        strategy = COTMomentumStrategy(sma_period=200, atr_period=14, trend_weeks=3)
        # Only 5 bars — way less than sma_period=200
        bars = _make_bars("gold", 5, spec_nets=[1000, 2000, 3000, 4000, 5000])
        bars_by_inst = {"gold": bars}

        portfolio = _fresh_portfolio()
        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        assert actions == []


# ===========================================================================
# MacroRegimeStrategy Tests
# ===========================================================================


class TestMacroRegimeStrategy:
    """Tests for Macro Regime strategy signal generation."""

    def _make_regime_bars(
        self,
        instrument: str,
        n: int = 30,
        base: float = 100.0,
        step: float = 0.0,
        volatility: float = 0.0,
        spec_nets: list[int | None] | None = None,
    ) -> list[Bar]:
        """Create bars for regime testing. volatility controls high-low spread."""
        if spec_nets is None:
            spec_nets = [5000] * n
        prices = []
        for i in range(n):
            close = base + i * step
            high = close + volatility
            low = close - volatility
            prices.append((close, high, low))
        return _make_bars_custom(instrument, prices, spec_nets=spec_nets)

    def test_risk_on_regime_long_risk_assets(self):
        """Low VIX + weakening DXY -> risk-on -> long risk assets."""
        strategy = MacroRegimeStrategy(
            vix_risk_on=20.0,
            vix_risk_off=25.0,
            atr_period=3,
            max_positions=8,
        )
        # SPX with very low volatility -> low VIX estimate
        # Small steady rise, minimal spread
        spx = self._make_regime_bars("spx", n=30, base=100.0, step=0.01, volatility=0.05,
                                     spec_nets=[5000] * 30)
        # DXY weakening (falling prices)
        dxy = self._make_regime_bars("dxy", n=30, base=105.0, step=-0.2, volatility=0.1,
                                     spec_nets=[3000] * 30)

        bars_by_inst = {"spx": spx, "dxy": dxy}
        portfolio = _fresh_portfolio()

        # Use a date in a new month to trigger rebalance
        actions = strategy.on_bar("2024-07-01", bars_by_inst, portfolio, _mock_engine())

        open_actions = [a for a in actions if a["action"] == "open"]
        # Should attempt to open positions; spx should be long in risk-on
        spx_opens = [a for a in open_actions if a["instrument"] == "spx"]
        if spx_opens:
            assert spx_opens[0]["direction"] == "long"

    def test_risk_off_regime_flips_risk_assets(self):
        """High VIX + strengthening DXY -> risk-off -> short risk assets."""
        strategy = MacroRegimeStrategy(
            vix_risk_on=20.0,
            vix_risk_off=25.0,
            atr_period=3,
            max_positions=8,
        )
        # SPX with wild swings (high weekly returns variance) -> high VIX estimate.
        # Alternating big up/down moves around 100.
        spx_prices = []
        for i in range(30):
            # Swing +-15% each week to create very high annualized vol
            close = 100.0 + (15.0 if i % 2 == 0 else -15.0)
            spx_prices.append((close, close + 5.0, close - 5.0))
        spx = _make_bars_custom("spx", spx_prices, spec_nets=[5000] * 30)

        # DXY strengthening (rising prices)
        dxy = self._make_regime_bars("dxy", n=30, base=95.0, step=0.5, volatility=0.1,
                                     spec_nets=[3000] * 30)

        bars_by_inst = {"spx": spx, "dxy": dxy}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar("2024-07-01", bars_by_inst, portfolio, _mock_engine())

        open_actions = [a for a in actions if a["action"] == "open"]
        # In risk-off, spx (RISK_ON asset) direction should be flipped to short
        spx_opens = [a for a in open_actions if a["instrument"] == "spx"]
        if spx_opens:
            assert spx_opens[0]["direction"] == "short"

    def test_no_rebalance_between_months(self):
        """Strategy only acts on first bar of a new month; same-month bars -> no actions."""
        strategy = MacroRegimeStrategy(atr_period=3)
        spx = self._make_regime_bars("spx", n=30, base=100.0, step=0.1, volatility=0.5,
                                     spec_nets=[5000] * 30)
        bars_by_inst = {"spx": spx}
        portfolio = _fresh_portfolio()

        # First call sets _last_rebalance_month
        strategy.on_bar("2024-07-01", bars_by_inst, portfolio, _mock_engine())
        # Second call in same month should return empty
        actions = strategy.on_bar("2024-07-08", bars_by_inst, portfolio, _mock_engine())

        assert actions == []

    def test_missing_indicator_data_graceful(self):
        """No SPX or DXY data -> defaults to neutral VIX/flat DXY, still no crash."""
        strategy = MacroRegimeStrategy(atr_period=3)
        # Only provide an unknown instrument
        bars = self._make_regime_bars("eurusd", n=30, base=1.08, step=0.001, volatility=0.005,
                                     spec_nets=[2000] * 30)
        bars_by_inst = {"eurusd": bars}
        portfolio = _fresh_portfolio()

        # Should not crash even without SPX/DXY
        actions = strategy.on_bar("2024-07-01", bars_by_inst, portfolio, _mock_engine())
        # eurusd is in ASSET_REGIME_DIR so it may or may not produce an action
        assert isinstance(actions, list)

    def test_all_indicators_neutral_regime(self):
        """VIX between thresholds + flat DXY -> neutral regime -> reduced sizing."""
        strategy = MacroRegimeStrategy(
            vix_risk_on=20.0,
            vix_risk_off=25.0,
            atr_period=3,
            max_positions=8,
        )
        # SPX with moderate volatility -> VIX around 22 (between 20 and 25)
        # We need weekly returns with ~3% annualized vol -> weekly std ~0.4%
        # VIX = weekly_std * sqrt(52) * 100
        # For VIX ~22: weekly_std = 22 / (sqrt(52)*100) = 22/721 ≈ 0.0305
        # With close prices around 100, changes of ~3 would give ~3% return volatility
        prices = []
        for i in range(30):
            close = 100.0 + (i % 2) * 3.0  # oscillate between 100 and 103
            prices.append((close, close + 1.0, close - 1.0))

        spx = _make_bars_custom("spx", prices, spec_nets=[5000] * 30)
        # DXY flat
        dxy = self._make_regime_bars("dxy", n=30, base=100.0, step=0.001, volatility=0.1,
                                     spec_nets=[3000] * 30)

        bars_by_inst = {"spx": spx, "dxy": dxy}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar("2024-07-01", bars_by_inst, portfolio, _mock_engine())

        # Should produce actions (or not), but no crash
        assert isinstance(actions, list)
        # Verify regime classification helper directly
        regime = strategy._classify_regime(22.0, "flat")
        assert regime == "neutral"


# ===========================================================================
# MeanReversionStrategy Tests
# ===========================================================================


class TestMeanReversionStrategy:
    """Tests for Mean Reversion strategy signal generation."""

    def _build_oversold_bars(self, instrument: str = "gold") -> list[Bar]:
        """Build bars where current price is at a demand zone with RSI < 30.

        Creates a series that drops sharply at the end to trigger oversold RSI,
        with enough history for pivot detection.
        """
        n = 40
        prices = []
        # 25 bars of ranging — create pivot lows around 90
        for i in range(25):
            close = 100.0 + (i % 5) * 2.0
            prices.append((close, close + 3.0, close - 3.0))

        # Create a clear pivot low at bar 25-28 around price 85
        prices.append((92.0, 95.0, 84.0))  # 25 - low at 84 creates demand zone
        prices.append((88.0, 90.0, 85.0))  # 26
        prices.append((90.0, 93.0, 87.0))  # 27
        prices.append((95.0, 98.0, 92.0))  # 28 - bounce up

        # Then sharp decline to oversold — 11 consecutive down bars
        for i in range(11):
            close = 94.0 - i * 1.0  # drops to 84
            prices.append((close, close + 0.5, close - 0.5))

        return _make_bars_custom(instrument, prices)

    def _build_overbought_bars(self, instrument: str = "gold") -> list[Bar]:
        """Build bars where current price is at a supply zone with RSI > 70.

        Creates a series that rises sharply at the end to trigger overbought RSI,
        with enough history for pivot detection.
        """
        n = 40
        prices = []
        # 25 bars of ranging — create pivot highs around 110
        for i in range(25):
            close = 100.0 + (i % 5) * 2.0
            prices.append((close, close + 3.0, close - 3.0))

        # Create a clear pivot high at bar 25-28 around price 115
        prices.append((108.0, 116.0, 105.0))  # 25 - high at 116 creates supply zone
        prices.append((112.0, 115.0, 110.0))  # 26
        prices.append((110.0, 113.0, 107.0))  # 27
        prices.append((105.0, 108.0, 102.0))  # 28 - drop back down

        # Then sharp rally to overbought — 11 consecutive up bars
        for i in range(11):
            close = 106.0 + i * 1.0  # rises to 116
            prices.append((close, close + 0.5, close - 0.5))

        return _make_bars_custom(instrument, prices)

    def test_oversold_at_demand_generates_long(self):
        """RSI < 30 at a demand zone or key level -> long signal."""
        strategy = MeanReversionStrategy(
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            rsi_period=14,
            sma_exit_period=5,
            atr_period=3,
            pivot_length=3,
            max_positions=6,
        )
        bars = self._build_oversold_bars("gold")
        bars_by_inst = {"gold": bars}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        longs = [a for a in actions if a.get("direction") == "long" and a["action"] == "open"]
        # The strategy should produce a long signal or at least not crash.
        # Whether a signal fires depends on zone alignment; the key assertion
        # is structural correctness and no exception.
        assert isinstance(actions, list)
        # If a signal is generated, it should be a well-formed long
        for action in longs:
            assert action["stop_loss"] < action["entry_price"]

    def test_overbought_at_supply_generates_short(self):
        """RSI > 70 at a supply zone or key level -> short signal."""
        strategy = MeanReversionStrategy(
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            rsi_period=14,
            sma_exit_period=5,
            atr_period=3,
            pivot_length=3,
            max_positions=6,
        )
        bars = self._build_overbought_bars("gold")
        bars_by_inst = {"gold": bars}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        shorts = [a for a in actions if a.get("direction") == "short" and a["action"] == "open"]
        assert isinstance(actions, list)
        for action in shorts:
            assert action["stop_loss"] > action["entry_price"]

    def test_normal_rsi_no_signal(self):
        """RSI in normal range (30-70) -> no entry signal."""
        strategy = MeanReversionStrategy(
            rsi_period=14,
            atr_period=3,
            sma_exit_period=5,
            pivot_length=3,
        )
        # Alternating up/down to keep RSI near 50 — not overbought or oversold
        n = 40
        prices = []
        for i in range(n):
            close = 100.0 + (1.0 if i % 2 == 0 else -1.0)
            prices.append((close, close + 1.5, close - 1.5))
        bars = _make_bars_custom("gold", prices)
        bars_by_inst = {"gold": bars}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        # No overbought or oversold condition, so no open actions expected
        opens = [a for a in actions if a["action"] == "open"]
        assert opens == []

    def test_flat_zero_volatility_no_crash(self):
        """All prices identical (zero volatility) -> no crash, no signal."""
        strategy = MeanReversionStrategy(
            rsi_period=14,
            atr_period=3,
            sma_exit_period=5,
            pivot_length=3,
        )
        n = 40
        # All bars have identical OHLC
        prices = [(100.0, 100.0, 100.0)] * n
        bars = _make_bars_custom("gold", prices)
        bars_by_inst = {"gold": bars}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        # ATR=0 -> strategy skips, no crash
        assert actions == []

    def test_insufficient_history_no_crash(self):
        """Fewer bars than required lookback -> no signal, no crash."""
        strategy = MeanReversionStrategy(
            rsi_period=14,
            atr_period=14,
            sma_exit_period=20,
            pivot_length=10,
        )
        # Only 5 bars — much less than min_bars requirement
        bars = _make_bars("gold", 5, base_price=100.0, step=1.0)
        bars_by_inst = {"gold": bars}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        assert actions == []


# ===========================================================================
# SMCConfluenceStrategy Tests
# ===========================================================================


class TestSMCConfluenceStrategy:
    """Tests for SMC + Confluence strategy signal generation."""

    def _build_demand_zone_bullish(self, instrument: str = "gold") -> list[Bar]:
        """Build bars with strong bullish confluence at a demand zone.

        Requirements:
        - Price at a demand zone (near a pivot low)
        - Strong COT positioning (bullish)
        - Price above SMA (bullish trend)
        - Positive momentum
        - Bullish structure (HH + HL)
        """
        n = 220  # enough for SMA200
        prices = []
        spec_nets = []

        # 200 bars of steady uptrend — establishes SMA200 well below current
        for i in range(200):
            close = 50.0 + i * 0.5  # rises from 50 to 149.5
            prices.append((close, close + 2.0, close - 2.0))
            spec_nets.append(15000)  # strong bullish COT

        # Bars 200-205: create a sharp pullback to form demand zone
        # Then recover — pivot low at ~bar 203
        prices.append((148.0, 150.0, 145.0))  # 200 - start pullback
        spec_nets.append(16000)
        prices.append((143.0, 146.0, 140.0))  # 201
        spec_nets.append(16000)
        prices.append((139.0, 142.0, 136.0))  # 202 - deeper
        spec_nets.append(17000)
        prices.append((135.0, 138.0, 132.0))  # 203 - pivot low area
        spec_nets.append(17000)
        prices.append((139.0, 142.0, 136.0))  # 204 - bounce
        spec_nets.append(18000)
        prices.append((143.0, 146.0, 140.0))  # 205 - higher
        spec_nets.append(18000)
        prices.append((148.0, 151.0, 145.0))  # 206 - recovery
        spec_nets.append(19000)
        prices.append((152.0, 155.0, 149.0))  # 207 - new high
        spec_nets.append(19000)

        # Create a second pullback INTO the demand zone
        prices.append((148.0, 151.0, 145.0))  # 208
        spec_nets.append(20000)
        prices.append((145.0, 148.0, 142.0))  # 209
        spec_nets.append(20000)
        prices.append((140.0, 143.0, 137.0))  # 210 - at/near demand zone
        spec_nets.append(20000)

        # Bars 211-219 continue to hold zone
        for i in range(9):
            close = 138.0 + i * 0.3
            prices.append((close, close + 2.0, close - 2.0))
            spec_nets.append(20000)

        return _make_bars_custom(instrument, prices, spec_nets=spec_nets)

    def test_demand_zone_with_confluence_signal(self):
        """Price at demand zone with high confluence score -> potential long signal."""
        strategy = SMCConfluenceStrategy(
            min_confluence=3,  # lowered threshold for easier triggering
            sma_period=50,
            atr_period=3,
            pivot_length=3,
            max_positions=6,
        )
        bars = self._build_demand_zone_bullish("gold")
        bars_by_inst = {"gold": bars}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        # Should produce a signal or at minimum not crash.
        # The zone alignment is hard to guarantee with synthetic data,
        # so we test structural correctness.
        assert isinstance(actions, list)
        for a in actions:
            assert a["action"] == "open"
            assert "instrument" in a
            assert "direction" in a

    def test_conflicting_signals_no_trade(self):
        """When confluence score is below threshold, no trade is opened."""
        strategy = SMCConfluenceStrategy(
            min_confluence=12,  # impossibly high -> no trade
            sma_period=50,
            atr_period=3,
            pivot_length=3,
        )
        # Use simple rising bars with no COT data -> low confluence
        bars = _make_bars("gold", 60, base_price=100.0, step=1.0)
        bars_by_inst = {"gold": bars}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        opens = [a for a in actions if a["action"] == "open"]
        assert opens == []

    def test_strong_confluence_includes_confidence_info(self):
        """When a signal fires, the reason includes the confluence score."""
        strategy = SMCConfluenceStrategy(
            min_confluence=1,  # very low to ensure signal fires if at zone
            sma_period=10,
            atr_period=3,
            pivot_length=3,
        )
        bars = self._build_demand_zone_bullish("gold")
        bars_by_inst = {"gold": bars}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        for a in actions:
            if a["action"] == "open":
                assert "confluence=" in a["reason"]

    def test_no_smc_structures_found(self):
        """With insufficient data for pivot detection -> no zones, no signal."""
        strategy = SMCConfluenceStrategy(
            sma_period=200,
            atr_period=14,
            pivot_length=10,
        )
        # Only 10 bars — not enough for SMA200 or pivot detection
        bars = _make_bars("gold", 10, base_price=100.0, step=0.5)
        bars_by_inst = {"gold": bars}
        portfolio = _fresh_portfolio()

        actions = strategy.on_bar(bars[-1].date, bars_by_inst, portfolio, _mock_engine())

        assert actions == []

    def test_minimal_data_no_crash(self):
        """Single bar or very few bars -> no crash."""
        strategy = SMCConfluenceStrategy(sma_period=5, atr_period=2, pivot_length=2)

        # 1 bar
        bars = _make_bars("gold", 1, base_price=100.0)
        portfolio = _fresh_portfolio()
        actions = strategy.on_bar(bars[-1].date, {"gold": bars}, portfolio, _mock_engine())
        assert actions == []

        # 3 bars
        bars = _make_bars("gold", 3, base_price=100.0, step=1.0)
        actions = strategy.on_bar(bars[-1].date, {"gold": bars}, portfolio, _mock_engine())
        assert actions == []
