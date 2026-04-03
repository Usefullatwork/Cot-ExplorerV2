"""Intelligence routes — sentiment, propagation, attribution, microstructure.

Each endpoint calls pure analysis functions from ``src/analysis/``
with data fetched from the database.  No hardcoded responses.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from src.analysis.microstructure import liquidity_score, optimal_execution_window
from src.analysis.nlp_sentiment import headline_relevance, sentiment_score
from src.analysis.signal_propagation import build_propagation_graph
from src.db.engine import session_ctx
from src.db.models import (
    BacktestResult,
    BotPosition,
    GeoIntelArticle,
    MacroSnapshot,
    PipelineState,
    PriceDaily,
    Signal,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

_INSTRUMENTS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDNOK",
    "Gold", "Silver", "Brent", "WTI", "SPX", "NAS100", "VIX", "DXY",
]

# Typical spreads in pips (from src/trading/bot/config.py DEFAULT_SPREADS)
_TYPICAL_SPREADS: dict[str, float] = {
    "EURUSD": 1.2, "USDJPY": 1.4, "GBPUSD": 1.8, "AUDUSD": 1.6,
    "USDCHF": 1.6, "USDNOK": 4.0,
    "Gold": 3.0, "Silver": 3.5, "Brent": 4.0, "WTI": 4.0,
    "SPX": 5.0, "NAS100": 8.0, "VIX": 5.0, "DXY": 3.0,
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _current_hour_cet() -> int:
    """Current hour in CET (UTC+1, simplified — ignores summer time)."""
    return (datetime.now(timezone.utc) + timedelta(hours=1)).hour


def _current_vix() -> float:
    """Latest VIX from pipeline_state, then macro_snapshots, else 15.0."""
    with session_ctx() as session:
        state = session.query(PipelineState).first()
        if state and state.vix_price:
            return state.vix_price
        macro = (
            session.query(MacroSnapshot)
            .filter(MacroSnapshot.vix_price.isnot(None))
            .order_by(MacroSnapshot.generated_at.desc())
            .first()
        )
        if macro and macro.vix_price:
            return macro.vix_price
    return 15.0


def _parse_published_at(raw: str, fallback: datetime) -> datetime:
    """Parse a published_at string into a tz-aware datetime."""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        if fallback.tzinfo is None:
            return fallback.replace(tzinfo=timezone.utc)
        return fallback


def _get_trade_pnl(trade: dict) -> float:
    """Extract PnL from a trade dict (prefer pnl_usd, fallback pnl_pips)."""
    if "pnl_usd" in trade:
        return float(trade["pnl_usd"])
    return float(trade.get("pnl_pips", 0.0))


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/sentiment",
    summary="Per-instrument sentiment scores",
    description=(
        "NLP sentiment scores per instrument (-1 bearish to +1 bullish), "
        "computed from geo-intel article headlines."
    ),
)
async def get_sentiment() -> dict:
    """Per-instrument sentiment from NLP analysis of news headlines."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=72)

    with session_ctx() as session:
        articles = (
            session.query(GeoIntelArticle)
            .filter(GeoIntelArticle.fetched_at >= cutoff)
            .all()
        )

    headlines: list[dict] = []
    for art in articles:
        pub = _parse_published_at(art.published_at, art.fetched_at or now)
        age_hours = max(0.0, (now - pub).total_seconds() / 3600)
        headlines.append({"text": art.title, "age_hours": age_hours})

    scores = []
    for inst in _INSTRUMENTS:
        result = sentiment_score(inst, headlines)
        n_relevant = sum(
            1 for h in headlines if headline_relevance(h["text"], inst) > 0
        )
        scores.append({
            "instrument": inst,
            "score": round(result.aggregate_score, 2),
            "label": result.bias.lower(),
            "sources": n_relevant,
        })

    return {
        "scores": scores,
        "model": "nlp_sentiment_v1",
        "timestamp": now.isoformat(),
        "is_live": len(headlines) > 0,
    }


@router.get(
    "/propagation",
    summary="Signal propagation edges",
    description=(
        "Cross-asset signal propagation graph built from lagged "
        "correlations on daily returns."
    ),
)
async def get_propagation() -> dict:
    """Signal propagation edges with lag and strength."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=252)
    ).strftime("%Y-%m-%d")

    with session_ctx() as session:
        rows = (
            session.query(PriceDaily)
            .filter(PriceDaily.date >= cutoff)
            .order_by(PriceDaily.instrument, PriceDaily.date.asc())
            .all()
        )

    # Group closes by instrument
    closes: dict[str, list[float]] = {}
    for row in rows:
        closes.setdefault(row.instrument, []).append(row.close)

    # Compute daily returns (need >=20 days for meaningful correlation)
    returns: dict[str, list[float]] = {}
    for inst, prices in closes.items():
        if len(prices) >= 20:
            rets = [
                (prices[i] / prices[i - 1]) - 1.0
                for i in range(1, len(prices))
            ]
            returns[inst] = rets

    if len(returns) < 2:
        return {
            "edges": [],
            "total_nodes": 0,
            "total_edges": 0,
            "is_live": False,
        }

    graph = build_propagation_graph(returns, min_correlation=0.3, max_lag=5)

    edges = [
        {
            "source": e.source,
            "target": e.target,
            "lag_hours": e.lag_bars,
            "strength": round(abs(e.correlation), 2),
            "direction": "direct" if e.direction == "positive" else "inverse",
        }
        for e in graph.edges
    ]

    return {
        "edges": edges,
        "total_nodes": graph.n_instruments,
        "total_edges": graph.n_edges,
        "is_live": True,
    }


@router.get(
    "/attribution",
    summary="Performance attribution",
    description=(
        "Brinson-style return decomposition: per-signal PnL, "
        "regime breakdown, and sizing alpha."
    ),
)
async def get_attribution() -> dict:
    """Performance attribution — signal PnL, regime breakdown, sizing alpha."""
    from src.analysis.attribution import (
        attribute_by_regime,
        attribute_by_signal,
        attribute_by_sizing,
    )

    trades = _build_attribution_trades()

    if not trades:
        return {
            "signal_pnl": [],
            "regime_performance": [],
            "sizing_alpha": {
                "full_size_pnl_r": 0.0,
                "half_size_pnl_r": 0.0,
                "quarter_size_pnl_r": 0.0,
                "sizing_contribution_pct": 0.0,
                "description": "No closed trades for attribution analysis",
            },
            "total_pnl_r": 0.0,
            "total_trades": 0,
            "is_live": True,
            "no_data": True,
        }

    # Signal attribution (requires signal_flags on trades)
    signal_pnl: list[dict] = []
    has_flags = bool(trades[0].get("signal_flags"))
    if has_flags:
        try:
            sig_attrs = attribute_by_signal(trades)
            for a in sig_attrs:
                wins = sum(
                    1 for t in trades
                    if t.get("signal_flags", {}).get(a.signal_id)
                    and _get_trade_pnl(t) > 0
                )
                signal_pnl.append({
                    "signal": a.signal_id,
                    "pnl_r": round(a.total_contribution, 1),
                    "trades": a.trades_with_signal,
                    "win_rate": round(
                        wins / max(1, a.trades_with_signal), 2,
                    ),
                })
        except (KeyError, ValueError):
            logger.warning("Signal attribution failed — missing signal_flags")

    # Regime attribution
    regime_perf: list[dict] = []
    try:
        regime_attrs = attribute_by_regime(trades)
        regime_perf = [
            {
                "regime": r.regime,
                "pnl_r": round(r.total_pnl, 1),
                "trades": r.n_trades,
                "win_rate": round(r.win_rate, 2),
                "avg_rr": round(r.avg_pnl, 2),
            }
            for r in regime_attrs
        ]
    except (ValueError, KeyError):
        logger.warning("Regime attribution failed")

    # Sizing alpha
    sizing_alpha = {
        "full_size_pnl_r": 0.0,
        "half_size_pnl_r": 0.0,
        "quarter_size_pnl_r": 0.0,
        "sizing_contribution_pct": 0.0,
        "description": "Sizing data unavailable",
    }
    try:
        sa = attribute_by_sizing(trades)
        sizing_alpha = {
            "full_size_pnl_r": round(sa.actual_total_pnl, 1),
            "half_size_pnl_r": round(sa.equal_size_pnl, 1),
            "quarter_size_pnl_r": 0.0,
            "sizing_contribution_pct": round(sa.sizing_alpha_pct, 1),
            "description": (
                f"Position sizing added {sa.sizing_alpha_pct:.1f}% "
                "to total PnL vs equal sizing"
            ),
        }
    except (ValueError, KeyError):
        logger.warning("Sizing attribution failed")

    total_pnl = sum(_get_trade_pnl(t) for t in trades)

    return {
        "signal_pnl": signal_pnl,
        "regime_performance": regime_perf,
        "sizing_alpha": sizing_alpha,
        "total_pnl_r": round(total_pnl, 1),
        "total_trades": len(trades),
        "is_live": True,
    }


def _build_attribution_trades() -> list[dict]:
    """Build trade dicts from closed positions or backtest results."""
    with session_ctx() as session:
        # Prefer real closed positions
        positions = (
            session.query(BotPosition)
            .filter(
                BotPosition.status == "closed",
                BotPosition.pnl_pips.isnot(None),
            )
            .all()
        )
        if positions:
            return _positions_to_trades(positions, session)

        # Fall back to backtest results
        results = (
            session.query(BacktestResult)
            .filter(BacktestResult.pnl_pips.isnot(None))
            .all()
        )
        if results:
            return _backtest_to_trades(results, session)

    return []


def _positions_to_trades(
    positions: list[BotPosition],
    session: object,
) -> list[dict]:
    """Convert closed BotPositions to attribution trade dicts."""
    trades = []
    for pos in positions:
        trade: dict = {
            "pnl_usd": pos.pnl_usd or 0.0,
            "pnl_pips": pos.pnl_pips or 0.0,
            "lot_size": pos.lot_size,
            "direction": "long" if pos.direction == "bull" else "short",
            "entry_price": pos.entry_price,
            "exit_price": pos.exit_price or pos.entry_price,
            "regime": pos.vix_regime or "NORMAL",
        }
        # Attach signal_flags from the linked signal's score_details
        if pos.bot_signal_id and pos.bot_signal_rel:
            sig_id = pos.bot_signal_rel.signal_id
            if sig_id:
                signal = session.query(Signal).get(sig_id)
                if signal and signal.score_details:
                    try:
                        trade["signal_flags"] = json.loads(
                            signal.score_details,
                        )
                    except (json.JSONDecodeError, TypeError):
                        pass
        trades.append(trade)
    return trades


def _backtest_to_trades(
    results: list[BacktestResult],
    session: object,
) -> list[dict]:
    """Convert BacktestResults to attribution trade dicts."""
    trades = []
    for bt in results:
        pnl_pips = bt.pnl_pips or 0.0
        trade: dict = {
            "pnl_pips": pnl_pips,
            "pnl_usd": pnl_pips * 10.0,
            "lot_size": 1.0,
            "direction": "long" if bt.direction == "bull" else "short",
            "entry_price": bt.entry_price,
            "exit_price": bt.exit_price or bt.entry_price,
            "regime": "NORMAL",
        }
        signal = session.query(Signal).get(bt.signal_id)
        if signal:
            trade["regime"] = signal.vix_regime or "NORMAL"
            if signal.score_details:
                try:
                    trade["signal_flags"] = json.loads(
                        signal.score_details,
                    )
                except (json.JSONDecodeError, TypeError):
                    pass
        trades.append(trade)
    return trades


@router.get(
    "/microstructure",
    summary="Microstructure liquidity scores",
    description=(
        "Liquidity scores and optimal execution windows per instrument, "
        "computed from session timing and VIX levels."
    ),
)
async def get_microstructure() -> dict:
    """Liquidity scores and execution windows per instrument."""
    hour = _current_hour_cet()
    vix = _current_vix()
    now = datetime.now(timezone.utc)

    instruments = []
    for inst in _INSTRUMENTS:
        ls = liquidity_score(inst, hour, vix)
        ew = optimal_execution_window(inst)
        typical = _TYPICAL_SPREADS.get(inst, 3.0)
        # Scale spread by inverse of liquidity (lower liquidity = wider spread)
        adjusted_spread_bps = round(typical / max(ls.score, 0.1), 1)
        window_label = (
            f"{ew.session.replace('_', ' ').title()} "
            f"({ew.best_start_cet:02d}-{ew.best_end_cet:02d} CET)"
        )
        instruments.append({
            "instrument": inst,
            "liquidity_score": round(ls.score, 2),
            "spread_bps": adjusted_spread_bps,
            "optimal_window": window_label,
            "depth_rank": 0,
        })

    # Rank by liquidity score descending
    instruments.sort(key=lambda x: x["liquidity_score"], reverse=True)
    for rank, item in enumerate(instruments, 1):
        item["depth_rank"] = rank

    return {
        "instruments": instruments,
        "timestamp": now.isoformat(),
        "is_live": True,
    }
