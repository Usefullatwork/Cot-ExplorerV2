"""DB-backed data loader for the backtesting framework.

Loads price data from ``prices_daily`` and COT data from ``cot_positions``
tables, returning ``List[Bar]`` compatible with the JSON-based DataLoader.

This allows the WalkForwardOptimizer and BacktestEngine to run against
real DB data instead of static JSON files.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import CotPosition, PriceDaily

from .models import Bar

# CFTC symbol -> instrument key mapping (same as DataLoader.DEFAULT_COT_MAP)
_COT_SYMBOL_MAP: dict[str, str] = {
    "099741": "EURUSD",
    "096742": "USDJPY",
    "092741": "GBPUSD",
    "232741": "AUDUSD",
    "088691": "XAUUSD",
    "084691": "XAGUSD",
    "067651": "USOIL",
    "023651": "UKOIL",
    "133741": "SPX500",
    "209742": "NAS100",
    "098662": "DXY",
    "002602": "CORN",
    "001602": "WHEAT",
    "005602": "SOYBEAN",
    "083731": "SUGAR",
    "073732": "COFFEE",
    "080732": "COCOA",
}

# Reverse: instrument key -> list of CFTC symbols
_INSTRUMENT_TO_COT: dict[str, list[str]] = {}
for _cot, _inst in _COT_SYMBOL_MAP.items():
    _INSTRUMENT_TO_COT.setdefault(_inst, []).append(_cot)


class DbDataLoader:
    """Load price + COT data from the database for backtesting.

    Drop-in replacement for ``DataLoader`` when running backtests
    against live DB data instead of static JSON files.
    """

    def __init__(self, session: Session):
        self.session = session

    def available_instruments(self) -> list[str]:
        """List instruments that have price data in the DB."""
        stmt = (
            select(PriceDaily.instrument)
            .distinct()
            .order_by(PriceDaily.instrument)
        )
        rows = self.session.execute(stmt).scalars().all()
        return list(rows)

    def load_prices(self, instrument: str) -> list[dict]:
        """Load daily prices for an instrument from prices_daily table."""
        inst_upper = instrument.upper()
        stmt = (
            select(PriceDaily)
            .where(PriceDaily.instrument == inst_upper)
            .order_by(PriceDaily.date.asc())
        )
        rows = self.session.execute(stmt).scalars().all()
        return [
            {
                "date": r.date,
                "open": r.open_,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in rows
        ]

    def load_cot(self, instrument: str) -> list[dict]:
        """Load COT data for an instrument from cot_positions table."""
        inst_upper = instrument.upper()
        cot_symbols = _INSTRUMENT_TO_COT.get(inst_upper, [])

        if not cot_symbols:
            return []

        # Try each COT symbol with preferred report types
        report_pref = ["tff", "legacy", "disaggregated", "supplemental"]
        for cot_sym in cot_symbols:
            for report_type in report_pref:
                stmt = (
                    select(CotPosition)
                    .where(
                        CotPosition.symbol == cot_sym,
                        CotPosition.report_type == report_type,
                    )
                    .order_by(CotPosition.date.asc())
                )
                rows = self.session.execute(stmt).scalars().all()
                if rows:
                    return [
                        {
                            "date": r.date,
                            "spec_net": r.spec_net,
                            "spec_long": r.spec_long,
                            "spec_short": r.spec_short,
                            "oi": r.open_interest,
                        }
                        for r in rows
                    ]
        return []

    def load_merged(
        self,
        instrument: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[Bar]:
        """Load and merge price + COT data into Bar objects.

        Daily prices are merged with weekly COT data. For dates without
        a COT report, the nearest previous COT reading (within 10 days)
        is carried forward.
        """
        prices = self.load_prices(instrument)
        cot_data = self.load_cot(instrument)

        # Build COT lookup by date
        cot_by_date: dict[str, dict] = {}
        for row in cot_data:
            cot_by_date[row["date"]] = row

        bars: list[Bar] = []
        last_cot: Optional[dict] = None

        for row in prices:
            date_str = row["date"]

            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue

            # Find matching COT data (exact or nearest previous within 10 days)
            cot = cot_by_date.get(date_str)
            if cot is None:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                for offset in range(1, 11):
                    candidate = (d - timedelta(days=offset)).strftime("%Y-%m-%d")
                    if candidate in cot_by_date:
                        cot = cot_by_date[candidate]
                        break

            if cot is None:
                cot = last_cot
            else:
                last_cot = cot

            bar = Bar(
                date=date_str,
                instrument=instrument.upper(),
                price=row["close"],
                high=row.get("high", row["close"]),
                low=row.get("low", row["close"]),
                spec_net=cot["spec_net"] if cot else None,
                spec_long=cot["spec_long"] if cot else None,
                spec_short=cot["spec_short"] if cot else None,
                open_interest=cot["oi"] if cot else None,
            )
            bars.append(bar)

        return bars

    def date_range(self, instrument: str) -> tuple[str, str] | None:
        """Return (min_date, max_date) for an instrument, or None if empty."""
        inst_upper = instrument.upper()
        from sqlalchemy import func

        stmt = select(
            func.min(PriceDaily.date),
            func.max(PriceDaily.date),
        ).where(PriceDaily.instrument == inst_upper)
        row = self.session.execute(stmt).one_or_none()
        if row and row[0] and row[1]:
            return (row[0], row[1])
        return None

    def row_count(self, instrument: str) -> int:
        """Return number of price rows for an instrument."""
        from sqlalchemy import func

        inst_upper = instrument.upper()
        stmt = select(func.count(PriceDaily.id)).where(
            PriceDaily.instrument == inst_upper
        )
        return self.session.execute(stmt).scalar() or 0
