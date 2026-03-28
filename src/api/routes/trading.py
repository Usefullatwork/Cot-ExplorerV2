"""Trading bot API routes and TradingView webhook endpoint."""

from __future__ import annotations

import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.db import repository as repo
from src.security.input_validator import sanitize_string, validate_symbol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trading", tags=["trading"])


# ── Request / Response models ────────────────────────────────────────────────


class BotStatusResponse(BaseModel):
    active: bool
    broker_mode: str
    kill_switch_active: bool
    open_positions: int
    pnl_today_pips: float

class PositionResponse(BaseModel):
    id: int
    instrument: str
    direction: str
    status: str
    entry_price: float
    current_price: Optional[float] = None
    stop_loss: float
    target_1: float
    target_2: Optional[float] = None
    lot_size: float
    lot_tier: str
    vix_regime: str
    opened_at: str
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_pips: Optional[float] = None
    pnl_usd: Optional[float] = None
    pnl_rr: Optional[float] = None

class BotSignalResponse(BaseModel):
    id: int
    instrument: str
    direction: str
    grade: str
    score: int
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: Optional[float] = None
    source: str
    status: str
    received_at: str

class BotConfigResponse(BaseModel):
    active: bool
    broker_mode: str
    max_positions: int
    max_daily_trades: int
    risk_pct: float
    min_grade: str
    min_score: int
    kill_switch_active: bool
    kill_switch_reason: Optional[str] = None

class BotConfigUpdateRequest(BaseModel):
    broker_mode: Optional[str] = None
    max_positions: Optional[int] = Field(None, ge=1, le=20)
    max_daily_trades: Optional[int] = Field(None, ge=1, le=100)
    risk_pct: Optional[float] = Field(None, gt=0, le=0.05)
    min_grade: Optional[str] = None
    min_score: Optional[int] = Field(None, ge=0, le=12)

class KillSwitchRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

class StatusMessageResponse(BaseModel):
    status: str
    message: str

class TVAlertRequest(BaseModel):
    source: str = "tradingview"
    instrument: str
    direction: str
    score: int = Field(..., ge=0, le=12)
    grade: str
    entry: float
    sl: float
    t1: float
    t2: Optional[float] = None
    secret: Optional[str] = Field(None, description="Webhook secret for verification")
    timeframe: Optional[str] = None
    bid: Optional[float] = None
    ask: Optional[float] = None

class TVAlertResponse(BaseModel):
    status: str
    signal_id: int


# ── Helpers ──────────────────────────────────────────────────────────────────


def _position_to_dict(pos: Any) -> dict[str, Any]:
    """Convert a BotPosition ORM object to a JSON-friendly dict."""
    return {
        "id": pos.id, "instrument": pos.instrument, "direction": pos.direction,
        "status": pos.status, "entry_price": pos.entry_price,
        "current_price": pos.current_price, "stop_loss": pos.stop_loss,
        "target_1": pos.target_1, "target_2": pos.target_2,
        "lot_size": pos.lot_size, "lot_tier": pos.lot_tier,
        "vix_regime": pos.vix_regime,
        "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
        "closed_at": pos.closed_at.isoformat() if pos.closed_at else None,
        "exit_price": pos.exit_price, "exit_reason": pos.exit_reason,
        "pnl_pips": pos.pnl_pips, "pnl_usd": pos.pnl_usd, "pnl_rr": pos.pnl_rr,
    }


def _bot_signal_to_dict(sig: Any) -> dict[str, Any]:
    """Convert a BotSignal ORM object to a JSON-friendly dict."""
    return {
        "id": sig.id, "instrument": sig.instrument, "direction": sig.direction,
        "grade": sig.grade, "score": sig.score, "entry_price": sig.entry_price,
        "stop_loss": sig.stop_loss, "target_1": sig.target_1,
        "target_2": sig.target_2, "source": sig.source, "status": sig.status,
        "received_at": sig.received_at.isoformat() if sig.received_at else None,
    }


def _config_to_dict(config: Any) -> dict[str, Any]:
    """Convert a BotConfig ORM object to a JSON-friendly dict."""
    return {
        "active": config.active, "broker_mode": config.broker_mode,
        "max_positions": config.max_positions,
        "max_daily_trades": config.max_daily_trades,
        "risk_pct": config.risk_pct, "min_grade": config.min_grade,
        "min_score": config.min_score,
        "kill_switch_active": config.kill_switch_active,
        "kill_switch_reason": config.kill_switch_reason,
    }


# ── Trading endpoints ───────────────────────────────────────────────────────


@router.get("/status", response_model=BotStatusResponse, summary="Bot operational status")
def bot_status() -> dict[str, Any]:
    """Return current bot status: active state, broker mode, positions, and daily P&L."""
    config = repo.get_bot_config()
    open_positions = repo.get_bot_positions(status="open")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    closed_today = [
        p for p in repo.get_bot_positions(status="closed")
        if p.closed_at and p.closed_at.strftime("%Y-%m-%d") == today
    ]
    pnl_today = sum(p.pnl_pips or 0.0 for p in closed_today)
    return {
        "active": config.active, "broker_mode": config.broker_mode,
        "kill_switch_active": config.kill_switch_active,
        "open_positions": len(open_positions), "pnl_today_pips": pnl_today,
    }


@router.get("/positions", response_model=list[PositionResponse], summary="List active positions")
def list_positions() -> list[dict[str, Any]]:
    """Return all open and partial positions with current P&L."""
    positions = repo.get_bot_positions(status="open")
    partial = repo.get_bot_positions(status="partial")
    return [_position_to_dict(p) for p in list(positions) + list(partial)]


@router.get("/positions/{position_id}", response_model=PositionResponse, summary="Position detail")
def position_detail(position_id: int) -> dict[str, Any]:
    """Return a single position by ID."""
    pos = repo.get_bot_position(position_id)
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")
    return _position_to_dict(pos)


@router.get("/history", response_model=list[PositionResponse], summary="Closed trade history")
def trade_history(
    instrument: Optional[str] = Query(None, description="Filter by instrument key"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    """Return closed trade history with optional instrument filter."""
    try:
        if instrument:
            instrument = validate_symbol(instrument)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    closed = repo.get_bot_positions(status="closed", instrument=instrument)
    return [_position_to_dict(p) for p in closed[offset : offset + limit]]


@router.get("/signals", response_model=list[BotSignalResponse], summary="Signal queue")
def signal_queue() -> list[dict[str, Any]]:
    """Return pending and confirmed bot signals."""
    pending = repo.get_bot_signals(status="pending")
    confirmed = repo.get_bot_signals(status="confirmed")
    return [_bot_signal_to_dict(s) for s in list(pending) + list(confirmed)]


@router.post("/invalidate", response_model=StatusMessageResponse, summary="Activate kill switch")
def activate_kill_switch(body: KillSwitchRequest) -> dict[str, str]:
    """Emergency kill switch: sets kill_switch_active=True in BotConfig."""
    reason = sanitize_string(body.reason, max_length=500)
    repo.update_bot_config(
        kill_switch_active=True, kill_switch_reason=reason,
        kill_switch_at=datetime.now(timezone.utc),
    )
    repo.save_audit_log(event_type="kill_switch_activated", details={"reason": reason})
    logger.warning("Kill switch activated: %s", reason)
    return {"status": "ok", "message": f"Kill switch activated: {reason}"}


@router.get("/config", response_model=BotConfigResponse, summary="Current bot configuration")
def get_config() -> dict[str, Any]:
    """Return the current bot configuration."""
    return _config_to_dict(repo.get_bot_config())


@router.post("/config", response_model=BotConfigResponse, summary="Update bot configuration")
def update_config(body: BotConfigUpdateRequest) -> dict[str, Any]:
    """Partial update of bot configuration fields."""
    updates = body.model_dump(exclude_none=True)
    if "broker_mode" in updates and updates["broker_mode"] not in ("paper", "demo", "live"):
        raise HTTPException(status_code=400, detail="broker_mode must be paper, demo, or live")
    if "min_grade" in updates and updates["min_grade"] not in ("A+", "A", "B", "C"):
        raise HTTPException(status_code=400, detail="min_grade must be A+, A, B, or C")
    updates["updated_at"] = datetime.now(timezone.utc)
    config = repo.update_bot_config(**updates)
    audit_details = {k: v for k, v in updates.items() if k != "updated_at"}
    repo.save_audit_log(event_type="bot_config_updated", details=audit_details)
    return _config_to_dict(config)


@router.post("/start", response_model=StatusMessageResponse, summary="Start the bot")
def start_bot() -> dict[str, str]:
    """Start the bot (sets BotConfig.active=True). Placeholder for broker connection."""
    repo.update_bot_config(active=True, updated_at=datetime.now(timezone.utc))
    repo.save_audit_log(event_type="bot_started", details={"action": "start"})
    logger.info("Bot started")
    return {"status": "ok", "message": "Bot started"}


@router.post("/stop", response_model=StatusMessageResponse, summary="Stop the bot")
def stop_bot() -> dict[str, str]:
    """Stop the bot (sets BotConfig.active=False). Placeholder for broker disconnect."""
    repo.update_bot_config(active=False, updated_at=datetime.now(timezone.utc))
    repo.save_audit_log(event_type="bot_stopped", details={"action": "stop"})
    logger.info("Bot stopped")
    return {"status": "ok", "message": "Bot stopped"}


# ── TradingView webhook ─────────────────────────────────────────────────────

tv_router = APIRouter(prefix="/api/v1", tags=["webhook"])


@tv_router.post(
    "/webhook/tv-alert", response_model=TVAlertResponse,
    summary="Receive TradingView alert",
    description="Accepts a TradingView alert JSON, validates it, creates a pending BotSignal.",
)
async def tv_alert(body: TVAlertRequest) -> TVAlertResponse:
    """Receive a TradingView webhook alert and persist as a pending BotSignal."""
    tv_secret = os.environ.get("TV_WEBHOOK_SECRET", "")
    if tv_secret:
        if not body.secret or not hmac.compare_digest(body.secret, tv_secret):
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    try:
        instrument = validate_symbol(body.instrument)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if body.direction not in ("bull", "bear"):
        raise HTTPException(status_code=400, detail="direction must be bull or bear")

    signal = repo.save_bot_signal(
        source="tradingview", instrument=instrument, direction=body.direction,
        grade=body.grade, score=body.score, entry_price=body.entry,
        stop_loss=body.sl, target_1=body.t1, target_2=body.t2,
        status="pending", tv_payload=body.model_dump(),
    )
    repo.save_audit_log(
        event_type="tv_alert_received",
        details={"instrument": instrument, "direction": body.direction, "signal_id": signal.id},
    )
    logger.info("TV alert: %s %s (signal_id=%d)", instrument, body.direction, signal.id)
    return TVAlertResponse(status="ok", signal_id=signal.id)
