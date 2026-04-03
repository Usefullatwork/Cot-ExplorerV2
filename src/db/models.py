"""SQLAlchemy ORM models — 23 tables for the trading signal platform."""

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

    __table_args__ = (Index("ix_macro_generated", "generated_at"),)


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


# ---------------------------------------------------------------------------
# 11. BotConfig
# ---------------------------------------------------------------------------
class BotConfig(Base):
    """Trading bot configuration with master on/off, broker mode, and risk limits.

    A single row controls the bot's operational parameters including
    position limits, risk percentage, minimum signal quality, and a
    kill-switch for emergency shutdown.
    """

    __tablename__ = "bot_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    active = Column(Boolean, default=False, nullable=False)  # master on/off
    broker_mode = Column(String(16), default="paper", nullable=False)  # paper/demo/live
    max_positions = Column(Integer, default=3, nullable=False)
    max_daily_trades = Column(Integer, default=10, nullable=False)
    risk_pct = Column(Float, default=0.01, nullable=False)  # 1% risk per trade
    min_grade = Column(String(4), default="B", nullable=False)
    min_score = Column(Integer, default=6, nullable=False)
    kill_switch_active = Column(Boolean, default=False)
    kill_switch_reason = Column(Text, nullable=True)
    kill_switch_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# 12. BotSignal
# ---------------------------------------------------------------------------
class BotSignal(Base):
    """Inbound trading signal received by the bot for confirmation or rejection.

    Links optionally to an analysis ``Signal`` and stores entry/SL/target
    levels, source (pipeline or TradingView webhook), and confirmation
    status with rejection reason if applicable.
    """

    __tablename__ = "bot_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)
    received_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    source = Column(String(32), nullable=False)  # "pipeline" or "tradingview"
    instrument = Column(String(32), nullable=False)
    direction = Column(String(8), nullable=False)  # bull/bear
    grade = Column(String(4), nullable=False)
    score = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    target_1 = Column(Float, nullable=False)
    target_2 = Column(Float, nullable=True)
    status = Column(String(16), nullable=False, default="pending")  # pending/confirmed/rejected/expired
    confirmed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    tv_payload = Column(Text, nullable=True)  # raw TradingView JSON
    gate_log = Column(Text, nullable=True)  # JSON array of gate results
    automation_level = Column(String(8), nullable=True)  # "A+"/"A"/"B"/"blocked"
    reasoning_json = Column(Text, nullable=True)  # JSON: SignalReasoning output

    signal_rel = relationship("Signal")

    __table_args__ = (
        Index("ix_bot_signal_status", "status"),
        Index("ix_bot_signal_instrument", "instrument"),
        Index("ix_bot_signal_received", "received_at"),
    )


# ---------------------------------------------------------------------------
# 13. BotPosition
# ---------------------------------------------------------------------------
class BotPosition(Base):
    """Live or closed trading position managed by the bot.

    Tracks entry/exit prices, lot sizing (full/half/quarter), VIX regime,
    partial close state (T1 hit), candle-based exit rules, and realised
    PnL in pips, USD, and risk-reward multiples.
    """

    __tablename__ = "bot_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_signal_id = Column(Integer, ForeignKey("bot_signals.id"), nullable=True)
    broker_position_id = Column(String(64), nullable=True)  # broker's position reference
    instrument = Column(String(32), nullable=False)
    direction = Column(String(8), nullable=False)
    opened_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime, nullable=True)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=False)
    target_1 = Column(Float, nullable=False)
    target_2 = Column(Float, nullable=True)
    lot_size = Column(Float, nullable=False)
    lot_tier = Column(String(16), nullable=False)  # full/half/quarter
    vix_regime = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="open")  # open/partial/closed
    t1_hit = Column(Boolean, default=False)
    t1_closed_pct = Column(Float, default=0.0)
    candles_since_entry = Column(Integer, default=0)
    exit_reason = Column(String(32), nullable=True)  # t1/t2/stop_loss/ema9_cross/candle_8/...
    pnl_pips = Column(Float, nullable=True)
    pnl_usd = Column(Float, nullable=True)
    pnl_rr = Column(Float, nullable=True)

    bot_signal_rel = relationship("BotSignal")

    __table_args__ = (
        Index("ix_bot_pos_status", "status"),
        Index("ix_bot_pos_instrument", "instrument"),
        Index("ix_bot_pos_opened", "opened_at"),
    )


# ---------------------------------------------------------------------------
# 14. BotTradeLog
# ---------------------------------------------------------------------------
class BotTradeLog(Base):
    """Immutable event log for all bot trading activity.

    Records order submissions, fills, partial closes, stop-loss hits,
    target hits, EMA exits, candle-rule exits, kill-switch activations,
    geopolitical spikes, errors, and connection events with a JSON
    ``details`` payload.
    """

    __tablename__ = "bot_trade_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    position_id = Column(Integer, ForeignKey("bot_positions.id"), nullable=True)
    event_type = Column(String(32), nullable=False)  # order_sent/fill/sl_hit/t1_hit/...
    details = Column(Text, nullable=True)  # JSON

    position_rel = relationship("BotPosition")

    __table_args__ = (
        Index("ix_trade_log_ts", "timestamp"),
        Index("ix_trade_log_event", "event_type"),
        Index("ix_trade_log_position", "position_id"),
    )


# ---------------------------------------------------------------------------
# 15. SeismicEvent
# ---------------------------------------------------------------------------
class SeismicEvent(Base):
    """USGS earthquake event relevant to mining regions.

    Stores magnitude, location, depth, and the classified mining region
    for earthquakes that may affect commodity supply chains.
    """

    __tablename__ = "seismic_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mag = Column(Float, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    depth_km = Column(Float, nullable=False)
    place = Column(String(256), nullable=False)
    event_time = Column(String(32), nullable=False)
    region = Column(String(64), nullable=True)
    url = Column(String(512), nullable=False)
    fetched_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("event_time", "place", name="uq_seismic_event_time_place"),
        Index("ix_seismic_region", "region"),
        Index("ix_seismic_fetched", "fetched_at"),
    )


# ---------------------------------------------------------------------------
# 16. ComexInventory
# ---------------------------------------------------------------------------
class ComexInventory(Base):
    """COMEX warehouse inventory snapshot for a single metal.

    Tracks registered/eligible/total ounces (or pounds for copper),
    coverage percentage, and a stress index (0-100) indicating
    delivery tightness.
    """

    __tablename__ = "comex_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metal = Column(String(16), nullable=False)  # gold, silver, copper
    registered = Column(Integer, nullable=False)
    eligible = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    coverage_pct = Column(Float, nullable=False)
    stress_index = Column(Float, nullable=False)
    fetched_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_comex_metal", "metal"),
        Index("ix_comex_fetched", "fetched_at"),
    )


# ---------------------------------------------------------------------------
# 17. GeoIntelArticle
# ---------------------------------------------------------------------------
class GeoIntelArticle(Base):
    """News article from geo-intelligence feeds relevant to trading.

    Stores headline, source, publication time, and category (gold,
    silver, copper, geopolitical) for commodity-related news.
    """

    __tablename__ = "geointel_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(512), nullable=False)
    url = Column(String(1024), nullable=False)
    source = Column(String(128), nullable=False)
    published_at = Column(String(64), nullable=False)
    category = Column(String(32), nullable=False)
    fetched_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("url", "category", name="uq_geointel_url_category"),
        Index("ix_geointel_category", "category"),
        Index("ix_geointel_fetched", "fetched_at"),
    )


# ---------------------------------------------------------------------------
# 18. SignalPerformance
# ---------------------------------------------------------------------------
class SignalPerformance(Base):
    """Post-hoc performance tracking for a generated signal.

    Links to the original Signal record and tracks whether the trade
    hit its target (HIT), missed (MISS), is still pending, or was
    neutral.  Records PnL in pips and close time.
    """

    __tablename__ = "signal_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, ForeignKey("signals.id", ondelete="CASCADE"), nullable=False)
    instrument = Column(String(32), nullable=False)
    direction = Column(String(8), nullable=False)
    grade = Column(String(4), nullable=False)
    score = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    result = Column(String(16), nullable=False, default="PENDING")  # HIT/MISS/PENDING/NEUTRAL
    closed_at = Column(DateTime, nullable=True)
    pnl_pips = Column(Float, nullable=True)
    risk_reward = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    signal_rel = relationship("Signal")

    __table_args__ = (
        Index("ix_sigperf_signal", "signal_id"),
        Index("ix_sigperf_result", "result"),
        Index("ix_sigperf_instrument", "instrument"),
    )


# ---------------------------------------------------------------------------
# 19. CorrelationSnapshot
# ---------------------------------------------------------------------------
class CorrelationSnapshot(Base):
    """Point-in-time correlation between two instruments.

    Stores the rolling Pearson correlation coefficient over a
    configurable window (default 20 days) for cross-market analysis.
    """

    __tablename__ = "correlation_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_a = Column(String(32), nullable=False)
    instrument_b = Column(String(32), nullable=False)
    correlation = Column(Float, nullable=False)
    window_days = Column(Integer, nullable=False, default=20)
    calculated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_corr_instruments", "instrument_a", "instrument_b"),
        Index("ix_corr_calculated", "calculated_at"),
    )


# ---------------------------------------------------------------------------
# 20. PipelineState
# ---------------------------------------------------------------------------
class PipelineState(Base):
    """Single-row cache of Layer 2 pipeline computation results.

    Stores the latest VaR, stress test, regime, signal weights, and other
    portfolio-level metrics computed by the Layer 2 runner.  Read by the
    gate orchestrator when evaluating pending signals.
    """

    __tablename__ = "pipeline_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    regime = Column(String(32), nullable=True)
    vix_price = Column(Float, nullable=True)
    var_95_pct = Column(Float, nullable=True)
    var_99_pct = Column(Float, nullable=True)
    cvar_95_pct = Column(Float, nullable=True)
    stress_worst_pct = Column(Float, nullable=True)
    stress_survives = Column(Boolean, nullable=True)
    correlation_max = Column(Float, nullable=True)
    open_position_count = Column(Integer, default=0)
    signal_weights_json = Column(Text, nullable=True)
    ensemble_quality = Column(String(16), nullable=True)
    kelly_cache_json = Column(Text, nullable=True)
    risk_parity_json = Column(Text, nullable=True)
    drift_detected = Column(Boolean, default=False)
    account_equity = Column(Float, nullable=True)
    peak_equity = Column(Float, nullable=True)
    layer1_last_run_at = Column(DateTime, nullable=True)
    layer2_last_run_at = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# 21. PipelineRun
# ---------------------------------------------------------------------------
class PipelineRun(Base):
    """Audit trail for pipeline executions (Layer 1, Layer 2, retrain).

    Each row records when a pipeline run started, finished, its status,
    and a JSON blob with per-stage details or error messages.
    """

    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    layer = Column(String(8), nullable=False)  # "layer1"/"layer2"/"retrain"
    status = Column(String(16), nullable=False)  # "running"/"ok"/"error"
    duration_sec = Column(Float, nullable=True)
    signals_processed = Column(Integer, default=0)
    details_json = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_pipeline_runs_started", "started_at"),
        Index("ix_pipeline_runs_layer", "layer"),
    )


# ---------------------------------------------------------------------------
# 21. TradeJournal
# ---------------------------------------------------------------------------
class TradeJournal(Base):
    """Trade journal entry with reasoning for each signal/trade.

    Records the full reasoning chain: signal scoring reasoning, gate
    decision reasoning, exit reasoning, and post-trade lessons learned.
    """

    __tablename__ = "trade_journal"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    signal_id = Column(Integer, ForeignKey("bot_signals.id"), nullable=True)
    position_id = Column(Integer, ForeignKey("bot_positions.id"), nullable=True)
    instrument = Column(String(32), nullable=False)
    direction = Column(String(8), nullable=False)
    grade = Column(String(4), nullable=False)
    score = Column(Integer, nullable=False)
    entry_reasoning = Column(Text, nullable=True)  # JSON: SignalReasoning
    gate_reasoning = Column(Text, nullable=True)  # JSON: gate detail array
    exit_reasoning = Column(Text, nullable=True)  # JSON: exit rule + reason
    outcome = Column(String(16), nullable=True)  # win/loss/breakeven/pending
    pnl_pips = Column(Float, nullable=True)
    pnl_rr = Column(Float, nullable=True)
    lessons = Column(Text, nullable=True)  # Free-text post-trade notes

    signal_rel = relationship("BotSignal")
    position_rel = relationship("BotPosition")

    __table_args__ = (
        Index("ix_journal_instrument", "instrument"),
        Index("ix_journal_created", "created_at"),
        Index("ix_journal_outcome", "outcome"),
    )


# ---------------------------------------------------------------------------
# 22. WfoRun
# ---------------------------------------------------------------------------
class WfoRun(Base):
    """Walk-forward optimization run metadata.

    Stores instrument, strategy filters, window settings, runtime,
    PBO score, and a JSON blob of the best combo and top rankings.
    """

    __tablename__ = "wfo_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    instrument = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False, default="running")  # running/ok/error
    train_months = Column(Integer, nullable=False, default=6)
    test_months = Column(Integer, nullable=False, default=2)
    window_mode = Column(String(16), nullable=False, default="sliding")
    total_windows = Column(Integer, default=0)
    total_combinations = Column(Integer, default=0)
    runtime_seconds = Column(Float, nullable=True)
    pbo_score = Column(Float, nullable=True)
    best_strategy = Column(String(64), nullable=True)
    best_timeframe = Column(String(8), nullable=True)
    best_params_json = Column(Text, nullable=True)  # JSON
    best_test_score = Column(Float, nullable=True)
    ranking_json = Column(Text, nullable=True)  # JSON: top 20 combos
    overfit_warnings_json = Column(Text, nullable=True)  # JSON: list of warning strings
    oos_summary_json = Column(Text, nullable=True)  # JSON: CPCV/PBO/holdout results
    error_message = Column(Text, nullable=True)

    window_results = relationship(
        "WfoWindowResult", back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_wfo_runs_instrument", "instrument"),
        Index("ix_wfo_runs_started", "started_at"),
        Index("ix_wfo_runs_status", "status"),
    )


# ---------------------------------------------------------------------------
# 21. WfoWindowResult
# ---------------------------------------------------------------------------
# 23. WfoWindowResult
# ---------------------------------------------------------------------------
class WfoWindowResult(Base):
    """Individual walk-forward window result (train or test).

    Stores per-window metrics for one strategy + timeframe + params
    combination within a WFO run.
    """

    __tablename__ = "wfo_window_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("wfo_runs.id", ondelete="CASCADE"), nullable=False)
    window_start = Column(String(10), nullable=False)
    window_end = Column(String(10), nullable=False)
    is_train = Column(Boolean, nullable=False)
    strategy = Column(String(64), nullable=False)
    timeframe = Column(String(8), nullable=False)
    params_json = Column(Text, nullable=True)  # JSON
    sharpe = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    total_trades = Column(Integer, default=0)
    total_return_pct = Column(Float, nullable=True)
    composite_score = Column(Float, nullable=False, default=0.0)

    run = relationship("WfoRun", back_populates="window_results")

    __table_args__ = (
        Index("ix_wfo_window_run", "run_id"),
        Index("ix_wfo_window_strategy", "strategy"),
        Index("ix_wfo_window_is_train", "is_train"),
    )
