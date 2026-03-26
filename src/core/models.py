"""Core Pydantic models for the trading signal platform."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Instrument(BaseModel):
    """Trading instrument definition."""

    key: str
    name: str
    symbol: str
    label: str
    category: str
    class_: str = Field(alias="klasse")
    session: str
    cot_market: Optional[str] = None
    stooq: Optional[str] = None
    twelvedata: Optional[str] = None
    finnhub: Optional[str] = None
    news_risk_on_dir: Optional[str] = None
    news_risk_off_dir: Optional[str] = None

    model_config = {"populate_by_name": True}


class OhlcBar(BaseModel):
    """A single (high, low, close) bar — the (h, l, c) tuple from v1."""

    high: float
    low: float
    close: float

    def as_tuple(self) -> tuple[float, float, float]:
        """Return as the (h, l, c) tuple used by v1 functions."""
        return (self.high, self.low, self.close)


class TaggedLevel(BaseModel):
    """A price level tagged with source and weight."""

    price: float
    source: str
    weight: int
    zone_top: Optional[float] = None
    zone_bottom: Optional[float] = None


class ScoreDetail(BaseModel):
    """Single criterion in the confluence scoring."""

    label: str
    passes: bool


class ScoringInput(BaseModel):
    """All inputs for 16-point confluence scoring.

    The first 12 boolean fields are the original criteria.
    Fields 13-16 use richer types and are resolved by helper functions
    in ``src.analysis.scoring``.
    """

    # --- Original 12 boolean criteria ---
    above_sma200: bool
    momentum_confirms: bool
    cot_confirms: bool
    cot_strong: bool
    at_level_now: bool
    htf_level_nearby: bool
    trend_congruent: bool
    no_event_risk: bool
    news_confirms: bool
    fund_confirms: bool
    bos_confirms: bool
    smc_struct_confirms: bool

    # --- New institutional-grade factors (13-16) ---
    direction: str = "bull"
    current_price: float = 0.0
    atr: float = 0.0
    order_blocks: list[dict] = Field(default_factory=list)
    fvgs: list[dict] = Field(default_factory=list)
    current_hour_cet: int = 12
    instrument_class: str = "A"
    instrument: str = ""
    open_signals: list[dict] = Field(default_factory=list)


class ScoringResult(BaseModel):
    """Output of the confluence scoring function."""

    score: int
    max_score: int
    grade: str
    grade_color: str
    timeframe_bias: str
    details: list[ScoreDetail]


class SetupL2L(BaseModel):
    """Level-to-level trade setup."""

    entry: float
    entry_curr: float
    sl: float
    sl_type: str
    t1: float
    t2: float
    rr_t1: float
    rr_t2: float
    min_rr: float
    risk_atr_d: float
    entry_dist_atr: float
    entry_name: str
    entry_level: float
    entry_weight: int
    t1_source: str
    t1_weight: int
    t1_quality: str
    status: str
    note: str
    timeframe: str
    session: Optional[str] = None


class SmcOutput(BaseModel):
    """Output from SMC analysis."""

    structure: str
    supply_zones: list[dict]
    demand_zones: list[dict]
    bos_levels: list[dict]
    last_swing_high: Optional[dict] = None
    last_swing_low: Optional[dict] = None


class MacroIndicator(BaseModel):
    """A single macro indicator reading."""

    price: float
    chg1d: float
    chg5d: float


class FearGreed(BaseModel):
    """CNN Fear & Greed index reading."""

    score: float
    rating: str


class NewsSentiment(BaseModel):
    """Aggregated news sentiment from RSS feeds."""

    score: float
    label: str
    top_headlines: list[str]
    key_drivers: list[dict]
    ro_count: int
    roff_count: int
    headlines_n: int
