"""Publish macro data as static JSON files in the exact v1 format."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = Path("data/macro")


def publish_static_json(
    macro_data: dict[str, Any],
    output_dir: str | Path | None = None,
) -> Path:
    """Write ``latest.json`` in the exact v1 format used by the frontend.

    Parameters
    ----------
    macro_data : dict
        Complete macro panel dict as produced by the pipeline.  Expected keys:
        ``date``, ``cot_date``, ``prices``, ``vix_regime``, ``dollar_smile``,
        ``trading_levels``, ``calendar``.
    output_dir : str or Path, optional
        Directory to write into.  Defaults to ``data/macro``.

    Returns
    -------
    Path
        Full path to the written file.
    """
    out = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    target = out / "latest.json"

    with open(target, "w", encoding="utf-8") as f:
        json.dump(macro_data, f, ensure_ascii=False, indent=2)

    logger.info("Published static JSON: %s (%d bytes)", target, target.stat().st_size)
    return target


def export_signal_log(output_dir: str | Path | None = None) -> Path:
    """Export signal performance log to ``data/signal_log.json``.

    Returns
    -------
    Path
        Full path to the written file.
    """
    from src.db.engine import session_scope
    from src.db.models import SignalPerformance
    from sqlalchemy import select

    out = Path(output_dir) if output_dir else Path("data")
    out.mkdir(parents=True, exist_ok=True)
    target = out / "signal_log.json"

    gen = session_scope()
    session = next(gen)
    try:
        rows = session.execute(
            select(SignalPerformance).order_by(SignalPerformance.created_at.desc()).limit(500)
        ).scalars().all()

        records = []
        for r in rows:
            records.append({
                "id": r.id, "signal_id": r.signal_id, "instrument": r.instrument,
                "direction": r.direction, "grade": r.grade, "score": r.score,
                "entry_price": r.entry_price, "result": r.result,
                "pnl_pips": r.pnl_pips, "risk_reward": r.risk_reward,
                "closed_at": r.closed_at.isoformat() if r.closed_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        with open(target, "w", encoding="utf-8") as f:
            json.dump({"signals": records, "count": len(records)}, f, ensure_ascii=False, indent=2)

        logger.info("Exported signal log: %s (%d records)", target, len(records))
        try:
            gen.send(None)
        except StopIteration:
            pass
        return target
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise


if __name__ == "__main__":
    # CLI entry-point: read from DB or fallback and write latest.json
    from src.db import repository as repo

    snap = repo.get_latest_macro()
    if snap and snap.full_json:
        data = json.loads(snap.full_json)
    else:
        # Fallback: try to read existing file
        fallback = _DEFAULT_OUTPUT_DIR / "latest.json"
        if fallback.exists():
            with open(fallback, encoding="utf-8") as f:
                data = json.load(f)
        else:
            logger.error("No macro data available in DB or on disk.")
            raise SystemExit(1)

    publish_static_json(data)
    logger.info(f"OK: {_DEFAULT_OUTPUT_DIR / 'latest.json'}")
