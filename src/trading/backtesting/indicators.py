"""
Technical indicator calculations for the backtesting framework.
All stdlib Python -- no numpy/pandas/scipy.
"""

from typing import List, Optional

from .models import Bar


class Indicators:
    """Technical indicator calculations operating on lists of Bar objects."""

    @staticmethod
    def sma(bars: List[Bar], period: int) -> Optional[float]:
        """Simple Moving Average of close prices over last `period` bars."""
        if len(bars) < period:
            return None
        return sum(b.close for b in bars[-period:]) / period

    @staticmethod
    def ema(bars: List[Bar], period: int) -> Optional[float]:
        """Exponential Moving Average of close prices."""
        if len(bars) < period + 1:
            return None
        k = 2.0 / (period + 1)
        closes = [b.close for b in bars]
        ema_val = sum(closes[:period]) / period
        for c in closes[period:]:
            ema_val = c * k + ema_val * (1 - k)
        return ema_val

    @staticmethod
    def atr(bars: List[Bar], period: int = 14) -> Optional[float]:
        """Average True Range."""
        if len(bars) < period + 1:
            return None
        trs = []
        for i in range(1, len(bars)):
            h, lo, pc = bars[i].high, bars[i].low, bars[i - 1].close
            tr = max(h - lo, abs(h - pc), abs(lo - pc))
            trs.append(tr)
        if len(trs) < period:
            return None
        return sum(trs[-period:]) / period

    @staticmethod
    def rsi(bars: List[Bar], period: int = 14) -> Optional[float]:
        """Relative Strength Index."""
        if len(bars) < period + 1:
            return None
        changes = [bars[i].close - bars[i - 1].close for i in range(1, len(bars))]
        if len(changes) < period:
            return None

        gains = [max(c, 0) for c in changes[-period:]]
        losses = [max(-c, 0) for c in changes[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def macd(bars: List[Bar], fast: int = 12, slow: int = 26, signal: int = 9):
        """MACD line, signal line, histogram. Returns (macd, signal, hist) or None."""
        if len(bars) < slow + signal:
            return None
        closes = [b.close for b in bars]

        def _ema(data, n):
            k = 2.0 / (n + 1)
            e = sum(data[:n]) / n
            result = [e]
            for v in data[n:]:
                e = v * k + e * (1 - k)
                result.append(e)
            return result

        ema_fast = _ema(closes, fast)
        ema_slow = _ema(closes, slow)

        # Align lengths
        diff = len(ema_fast) - len(ema_slow)
        macd_line = [ema_fast[i + diff] - ema_slow[i] for i in range(len(ema_slow))]

        if len(macd_line) < signal:
            return None

        sig_line = _ema(macd_line, signal)
        hist = macd_line[-1] - sig_line[-1]

        return (macd_line[-1], sig_line[-1], hist)

    @staticmethod
    def spec_net_change(bars: List[Bar], weeks: int = 3) -> Optional[int]:
        """Change in speculator net position over N weeks."""
        relevant = [b for b in bars if b.spec_net is not None]
        if len(relevant) < weeks + 1:
            return None
        return relevant[-1].spec_net - relevant[-(weeks + 1)].spec_net

    @staticmethod
    def spec_net_trend(bars: List[Bar], weeks: int = 3) -> Optional[str]:
        """Direction of spec_net over last N weeks: 'increasing', 'decreasing', or 'flat'."""
        relevant = [b for b in bars if b.spec_net is not None]
        if len(relevant) < weeks + 1:
            return None
        values = [b.spec_net for b in relevant[-(weeks + 1) :]]
        increases = sum(1 for i in range(1, len(values)) if values[i] > values[i - 1])
        decreases = sum(1 for i in range(1, len(values)) if values[i] < values[i - 1])
        if increases >= weeks:
            return "increasing"
        elif decreases >= weeks:
            return "decreasing"
        return "flat"

    @staticmethod
    def cot_pct(bar: Bar) -> Optional[float]:
        """Spec net as percentage of open interest."""
        if bar.spec_net is None or bar.open_interest is None or bar.open_interest == 0:
            return None
        return (bar.spec_net / bar.open_interest) * 100
