"""SQLAlchemy ORM models — 10 tables for the trading signal platform."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# 1. Instrument
# ---------------------------------------------------------------------------
class Instrument(Base):
    """Trading instrument definition (e.g. EURUSD, Gold, SPX).

    The primary key ``key`` is a short slug used across signals, prices,
    and COT data to link records to a single tradable asset.
    """

    __tablename__ = "instruments"

    key = Column(String(32), primary_key=True)
    name = Column(String(64), nullable=False)
    symbol = Column(String(32), nullable=False)
    label = Column(String(32), nullable=False)
    category = Column(String(32), nullable=False)
    class_ = Column("class", String(8), nullable=False)
    session = Column(String(64), nullable=False)
    cot_market = Column(String(64), nullable=True)
    active = Column(Boolean, default=True, nullable=False)

    prices_daily = relationship("PriceDaily", back_populates="instrument_rel", cascade="all, delete-orphan")
    prices_intraday = relationship("PriceIntraday", back_populates="instrument_rel", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="instrument_rel", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 2. PriceDaily
# ---------------------------------------------------------------------------
class PriceDaily(Base):
    """Daily OHLCV price bar for an instrument.

    Unique on (instrument, date).  Sources include Yahoo Finance,
    Stooq, Twelvedata, and Finnhub real-time quotes.
    """

    __tablename__ = "prices_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument = Column(String(32), ForeignKey("instruments.key"), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    open_ = Column("open", Float, nullable=True)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True)
    source = Column(String(32), nullable=True)

    instrument_rel = relationship("Instrument", back_populates="prices_daily")

    __table_args__ = (
        UniqueConstraint("instrument", "date", name="uq_price_daily_inst_date"),
        Index("ix_price_daily_instrument", "instrument"),
        Index("ix_price_daily_date", "date"),
    )


# ---------------------------------------------------------------------------
# 3. PriceIntraday
# ---------------------------------------------------------------------------
class PriceIntraday(Base):
    """Intraday price bar (15m, 1h, 4h) for an instrument.

    Unique on (instrument, timestamp, timeframe).
    """

    __tablename__ = "prices_intraday"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument = Column(String(32), ForeignKey("instruments.key"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    timeframe = Column(String(8), nullable=False)  # 15m, 1h, 4h
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    source = Column(String(32), nullable=True)

    instrument_rel = relationship("Instrument", back_populates="prices_intraday")

    __table_args__ = (
        UniqueConstraint("instrument", "timestamp", "timeframe", name="uq_price_intraday"),
        Index("ix_price_intraday_instrument", "instrument"),
        Index("ix_price_intraday_ts", "timestamp"),
    )


# ---------------------------------------------------------------------------
# 4. CotPosition
# ---------------------------------------------------------------------------
class CotPosition(Base):
    """CFTC Commitment of Traders position record.

    Stores speculator, commercial, and non-reportable long/short/net
    positions from four CFTC report types: TFF, legacy, disaggregated,
    and supplemental.  Unique on (symbol, report_type, date).
    """

    __tablename__ = "cot_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    market = Column(String(128), nullable=False)
    report_type = Column(String(32), nullable=False)  # tff, legacy, disaggregated, supplemental
    date = Column(String(10), nullable=False)
    open_interest = Column(Integer, nullable=False, default=0)
    change_oi = Column(Integer, nullable=False, default=0)
    spec_long = Column(Integer, nullable=False, default=0)
    spec_short = Column(Integer, nullable=False, default=0)
    spec_net = Column(Integer, nullable=False, default=0)
    comm_long = Column(Integer, nullable=False, default=0)
    comm_short = Column(Integer, nullable=False, default=0)
    comm_net = Column(Integer, nullable=False, default=0)
    nonrept_long = Column(Integer, nullable=False, default=0)
    nonrept_short = Column(Integer, nullable=False, default=0)
    nonrept_net = Column(Integer, nullable=False, default=0)
    change_spec_net = Column(Integer, nullable=False, default=0)
    category = Column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("symbol", "report_type", "date", name="uq_cot_sym_rpt_date"),
        Index("ix_cot_symbol", "symbol"),
        Index("ix_cot_date", "date"),
        Index("ix_cot_report_type", "report_type"),
    )


# ---------------------------------------------------------------------------
# 5. Signal
# ---------------------------------------------------------------------------
class Signal(Base):
    """Generated trading signal with confluence score, direction, and trade levels.

    Each signal links to an instrument and includes entry/SL/target prices,
    risk-reward ratios, VIX regime context, and a JSON ``score_details``
    breakdown of the individual confluence criteria.
    """

    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument = Column(String(32), ForeignKey("instruments.key"), nullable=False)
    generated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    direction = Column(String(8), nullable=False)  # bull / bear
    grade = Column(String(4), nullable=False)  # A+, A, B, C
    score = Column(Integer, nullable=False)
    timeframe_bias = Column(String(16), nullable=False)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_1 = Column(Float, nullable=True)
    target_2 = Column(Float, nullable=True)
    rr_t1 = Column(Float, nullable=True)
    rr_t2 = Column(Float, nullable=True)
    entry_weight = Column(Integer, nullable=True)
    t1_weight = Column(Integer, nullable=True)
    sl_type = Column(String(16), nullable=True)
    at_level_now = Column(Boolean, nullable=True)
    vix_regime = Column(String(16), nullable=True)
    pos_size = Column(String(16), nullable=True)
    score_details = Column(Text, nullable=True)  # JSON string
    metadata_ = Column("metadata", Text, nullable=True)  # JSON string

    instrument_rel = relationship("Instrument", back_populates="signals")

    backtest_results = relationship("BacktestResult", back_populates="signal_rel", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_signal_instrument", "instrument"),
        Index("ix_signal_generated", "generated_at"),
        Index("ix_signal_grade", "grade"),
        Index("ix_signal_score", "score"),
    )


# ---------------------------------------------------------------------------
# 6. BacktestResult
# ---------------------------------------------------------------------------
class BacktestResult(Base):
    """Result of backtesting a signal against subsequent price data.

    Records entry/exit prices, exit reason (t1_hit, t2_hit, stopped_out,
    expired), PnL in pips and risk-reward multiples, and trade duration.
    """

    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=False)
    instrument = Column(String(32), nullable=False)
    entry_date = Column(DateTime, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_date = Column(DateTime, nullable=True)
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String(32), nullable=True)  # t1_hit, t2_hit, stopped_out, expired
    pnl_pips = Column(Float, nullable=True)
    pnl_rr = Column(Float, nullable=True)
    duration_hours = Column(Float, nullable=True)
    direction = Column(String(8), nullable=False)
    grade = Column(String(4), nullable=False)
    score = Column(Integer, nullable=False)

    signal_rel = relationship("Signal", back_populates="backtest_results")

    __table_args__ = (
        Index("ix_backtest_instrument", "instrument"),
        Index("ix_backtest_entry_date", "entry_date"),
    )


# ---------------------------------------------------------------------------
# 7. Fundamental
# ---------------------------------------------------------------------------
class Fundamental(Base):
    """Macro-economic fundamental indicator snapshot.

    Tracks current and previous values for indicators like GDP, CPI,
    employment, and central bank rates, with a numeric score and
    directional trend label.
    """

    __tablename__ = "fundamentals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    indicator_key = Column(String(32), nullable=False)
    label = Column(String(128), nullable=False)
    current_value = Column(Float, nullable=True)
    previous_value = Column(Float, nullable=True)
    score = Column(Integer, nullable=False, default=0)
    trend = Column(String(16), nullable=True)
    date = Column(String(10), nullable=True)

    __table_args__ = (
        Index("ix_fundamental_key", "indicator_key"),
        Index("ix_fundamental_updated", "updated_at"),
    )


# ---------------------------------------------------------------------------
# 8. MacroSnapshot
# ---------------------------------------------------------------------------
class MacroSnapshot(Base):
    """Point-in-time snapshot of the macro environment.

    Captures VIX price and regime, Dollar Smile state, USD bias,
    Fear & Greed index, news sentiment, yield curve slope, and
    geopolitical conflict indicators.  The ``full_json`` column
    stores the complete macro panel used by the frontend.
    """

    __tablename__ = "macro_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    generated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    vix_price = Column(Float, nullable=True)
    vix_regime = Column(String(16), nullable=True)
    dollar_smile = Column(String(16), nullable=True)
    usd_bias = Column(String(32), nullable=True)
    fear_greed = Column(Float, nullable=True)
    news_sentiment = Column(Text, nullable=True)  # JSON
    yield_curve = Column(Float, nullable=True)
    conflicts = Column(Text, nullable=True)  # JSON
    full_json = Column(Text, nullable=True)  # JSON — complete macro panel

    __table_args__ = (
        Index("ix_macro_generated", "generated_at"),
    )


# ---------------------------------------------------------------------------
# 9. CalendarEvent
# ---------------------------------------------------------------------------
class CalendarEvent(Base):
    """Economic calendar event (e.g. FOMC, NFP, CPI release).

    Stores the event date, title, country, impact level, consensus
    forecast, previous and actual values, hours until the event,
    and a JSON list of affected instrument keys.
    """

    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False)
    title = Column(String(256), nullable=False)
    country = Column(String(8), nullable=False)
    impact = Column(String(16), nullable=False)
    forecast = Column(String(32), nullable=True)
    previous = Column(String(32), nullable=True)
    actual = Column(String(32), nullable=True)
    hours_away = Column(Float, nullable=True)
    affected_instruments = Column(Text, nullable=True)  # JSON list

    __table_args__ = (
        Index("ix_calendar_date", "date"),
        Index("ix_calendar_impact", "impact"),
    )


# ---------------------------------------------------------------------------
# 10. AuditLog
# ---------------------------------------------------------------------------
class AuditLog(Base):
    """Immutable audit log entry for tracking system events.

    Records webhook receipts, pipeline runs, data fetches, and
    other significant operations with a JSON ``details`` payload.
    """

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    event_type = Column(String(64), nullable=False)
    details = Column(Text, nullable=True)  # JSON

    __table_args__ = (
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_event_type", "event_type"),
    )
