"""Professional risk management: equity curve trading, daily limits,
consecutive loss handling, weekly caps, VIX halt.

All functions are pure — they accept values as parameters and return
a ``RiskCheckResult``.  No database or I/O calls.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskCheckResult:
    """Outcome of a single risk check.

    Attributes:
        allowed: Whether trading is permitted.
        reason: Human-readable explanation of the decision.
        recommended_size_multiplier: Sizing scalar — 1.0 means full size,
            0.5 means half size, 0.0 means blocked.
    """

    allowed: bool
    reason: str
    recommended_size_multiplier: float  # 1.0 = full, 0.5 = half, 0.0 = blocked


# ── Individual checks ─────────────────────────────────────────────────────


def check_equity_curve(
    peak_equity: float,
    current_equity: float,
    pause_threshold: float = 0.10,
    resume_threshold: float = 0.05,
) -> RiskCheckResult:
    """Equity-curve trading: pause when drawdown exceeds *pause_threshold*.

    Trading resumes only when drawdown recovers to within *resume_threshold*
    of the peak.

    Args:
        peak_equity: Highest account equity recorded.
        current_equity: Current account equity.
        pause_threshold: Drawdown fraction to trigger a pause (default 10 %).
        resume_threshold: Drawdown fraction to allow resumption (default 5 %).

    Returns:
        RiskCheckResult with ``allowed=False`` if drawdown is between the
        pause and resume thresholds, inclusive.
    """
    if peak_equity <= 0:
        return RiskCheckResult(True, "no equity history", 1.0)

    drawdown_pct = (peak_equity - current_equity) / peak_equity

    if drawdown_pct >= pause_threshold:
        return RiskCheckResult(
            False,
            f"equity curve pause: drawdown {drawdown_pct:.1%} >= {pause_threshold:.0%}",
            0.0,
        )
    if drawdown_pct >= resume_threshold:
        # Between resume and pause thresholds — scale down linearly.
        scale = 1.0 - (drawdown_pct - resume_threshold) / (pause_threshold - resume_threshold)
        return RiskCheckResult(
            True,
            f"equity curve caution: drawdown {drawdown_pct:.1%}",
            round(max(scale, 0.0), 2),
        )
    return RiskCheckResult(True, "equity curve healthy", 1.0)


def check_daily_loss_limit(
    losses_today: int,
    max_daily_losses: int = 3,
) -> RiskCheckResult:
    """Block trading after *max_daily_losses* losing trades in one day.

    Args:
        losses_today: Number of losing trades closed today.
        max_daily_losses: Threshold to halt trading (default 3).

    Returns:
        RiskCheckResult with ``allowed=False`` once the limit is reached.
    """
    if losses_today >= max_daily_losses:
        return RiskCheckResult(
            False,
            f"daily loss limit: {losses_today}/{max_daily_losses} losses",
            0.0,
        )
    return RiskCheckResult(True, "daily losses within limit", 1.0)


def check_consecutive_losses(consecutive_losses: int) -> RiskCheckResult:
    """Scale position size down after consecutive losses.

    - 0-1 losses: full size (1.0x)
    - 2 losses:   half size (0.5x)
    - 3+ losses:  quarter size (0.25x)

    Args:
        consecutive_losses: Number of consecutive losing trades.

    Returns:
        RiskCheckResult — always allowed, but multiplier decreases.
    """
    if consecutive_losses >= 3:
        return RiskCheckResult(
            True,
            f"consecutive losses ({consecutive_losses}): quarter size",
            0.25,
        )
    if consecutive_losses == 2:
        return RiskCheckResult(
            True,
            f"consecutive losses ({consecutive_losses}): half size",
            0.5,
        )
    return RiskCheckResult(True, "no loss streak", 1.0)


def check_weekly_loss_cap(
    weekly_pnl_pct: float,
    cap_pct: float = -5.0,
) -> RiskCheckResult:
    """Pause trading if weekly P&L drops below *cap_pct*.

    Args:
        weekly_pnl_pct: Realised P&L for the current week as a percentage
            (e.g. -3.5 means a 3.5 % loss).
        cap_pct: Threshold in percent (default -5.0 %).

    Returns:
        RiskCheckResult with ``allowed=False`` when cap is breached.
    """
    if weekly_pnl_pct <= cap_pct:
        return RiskCheckResult(
            False,
            f"weekly loss cap: {weekly_pnl_pct:.1f}% <= {cap_pct:.1f}%",
            0.0,
        )
    return RiskCheckResult(True, "weekly P&L within cap", 1.0)


def check_vix_halt(
    vix: float,
    halt_threshold: float = 40.0,
) -> RiskCheckResult:
    """Halt all trading when VIX exceeds *halt_threshold*.

    Args:
        vix: Current VIX index value.
        halt_threshold: VIX level above which trading is paused (default 40).

    Returns:
        RiskCheckResult with ``allowed=False`` when VIX > threshold.
    """
    if vix > halt_threshold:
        return RiskCheckResult(
            False,
            f"VIX halt: {vix:.1f} > {halt_threshold:.0f}",
            0.0,
        )
    return RiskCheckResult(True, "VIX within range", 1.0)


# ── Aggregate evaluator ───────────────────────────────────────────────────


def evaluate_risk(
    peak_equity: float,
    current_equity: float,
    losses_today: int,
    consecutive_losses: int,
    weekly_pnl_pct: float,
    vix: float,
    *,
    max_daily_losses: int = 3,
    pause_threshold: float = 0.10,
    resume_threshold: float = 0.05,
    weekly_cap_pct: float = -5.0,
    vix_halt_threshold: float = 40.0,
) -> RiskCheckResult:
    """Run all risk checks and return the most restrictive result.

    Individual multipliers stack multiplicatively.  If *any* check
    returns ``allowed=False`` the aggregate result is also blocked.

    Args:
        peak_equity: Highest recorded account equity.
        current_equity: Current account equity.
        losses_today: Losing trades closed today.
        consecutive_losses: Current consecutive-loss streak.
        weekly_pnl_pct: Realised weekly P&L percentage.
        vix: Current VIX index value.
        max_daily_losses: Daily loss limit (default 3).
        pause_threshold: Equity-curve pause drawdown (default 10 %).
        resume_threshold: Equity-curve resume drawdown (default 5 %).
        weekly_cap_pct: Weekly loss cap in percent (default -5.0 %).
        vix_halt_threshold: VIX halt level (default 40).

    Returns:
        Aggregate RiskCheckResult.
    """
    checks = [
        check_equity_curve(peak_equity, current_equity, pause_threshold, resume_threshold),
        check_daily_loss_limit(losses_today, max_daily_losses),
        check_consecutive_losses(consecutive_losses),
        check_weekly_loss_cap(weekly_pnl_pct, weekly_cap_pct),
        check_vix_halt(vix, vix_halt_threshold),
    ]

    combined_multiplier = 1.0
    reasons: list[str] = []

    for chk in checks:
        if not chk.allowed:
            return RiskCheckResult(False, chk.reason, 0.0)
        combined_multiplier *= chk.recommended_size_multiplier
        if chk.recommended_size_multiplier < 1.0:
            reasons.append(chk.reason)

    combined_multiplier = round(combined_multiplier, 4)

    if reasons:
        return RiskCheckResult(True, "; ".join(reasons), combined_multiplier)
    return RiskCheckResult(True, "all risk checks passed", combined_multiplier)
