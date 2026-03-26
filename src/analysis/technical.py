"""Technical analysis functions — pure, no side effects.

Extracted from v1 fetch_all.py lines 243-265.
"""

from __future__ import annotations

from src.core.models import OhlcBar

# ---------------------------------------------------------------------------
# Type alias: rows can be passed as list of OhlcBar *or* plain (h,l,c) tuples
# to stay compatible with v1 callers.  Internally we index [0]=h, [1]=l, [2]=c.
# ---------------------------------------------------------------------------
Row = tuple[float, float, float] | OhlcBar


def _h(r: Row) -> float:
    return r.high if isinstance(r, OhlcBar) else r[0]


def _l(r: Row) -> float:
    return r.low if isinstance(r, OhlcBar) else r[1]


def _c(r: Row) -> float:
    return r.close if isinstance(r, OhlcBar) else r[2]


def calc_atr(rows: list[Row], n: int = 14) -> float | None:
    """Average True Range over *n* periods.

    Requires at least n+1 rows.  Returns None if insufficient data.
    """
    if len(rows) < n + 1:
        return None
    trs = [
        max(
            _h(rows[i]) - _l(rows[i]),
            abs(_h(rows[i]) - _c(rows[i - 1])),
            abs(_l(rows[i]) - _c(rows[i - 1])),
        )
        for i in range(1, len(rows))
    ]
    return sum(trs[-n:]) / n


def calc_ema(closes: list[float], n: int = 9) -> float | None:
    """Exponential Moving Average over *n* periods.

    Requires at least n+1 values.  Returns None if insufficient data.
    """
    if len(closes) < n + 1:
        return None
    k = 2 / (n + 1)
    ema = sum(closes[:n]) / n
    for c in closes[n:]:
        ema = c * k + ema * (1 - k)
    return ema


def to_4h(rows_1h: list[Row]) -> list[tuple[float, float, float]]:
    """Aggregate 1-hour bars into 4-hour bars.

    Groups in non-overlapping windows of 4.  Returns plain (h, l, c) tuples.
    """
    out: list[tuple[float, float, float]] = []
    for i in range(0, len(rows_1h) - 3, 4):
        grp = rows_1h[i : i + 4]
        h = max(_h(r) for r in grp)
        lo = min(_l(r) for r in grp)
        c = _c(grp[-1])
        out.append((h, lo, c))
    return out
