"""Migrate v1 Cot-Explorer historical data into v2 SQLite database.

Imports:
- COT data from data/history/{report_type}/{year}.json -> cot_positions table
- Price snapshots from data/prices/ -> prices_daily table
- Replays scoring to seed signals table

Idempotent: skips existing records via unique constraints.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

from sqlalchemy.exc import IntegrityError

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.engine import get_engine, init_db
from src.db.models import CotPosition, PriceDaily


def migrate_cot_data(session, data_root: Path) -> int:
    """Import COT JSON files from data/history/{report_type}/{year}.json."""
    history_dir = data_root / "history"
    if not history_dir.exists():
        log.warning("COT history directory not found: %s", history_dir)
        return 0

    imported = 0
    skipped = 0

    for report_dir in sorted(history_dir.iterdir()):
        if not report_dir.is_dir():
            continue
        report_type = report_dir.name

        for year_file in sorted(report_dir.glob("*.json")):
            try:
                records = json.loads(year_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                log.warning("SKIP %s: %s", year_file.name, e)
                continue

            if not isinstance(records, list):
                records = [records] if isinstance(records, dict) else []

            batch = []
            for rec in records:
                try:
                    pos = CotPosition(
                        symbol=rec.get("symbol", rec.get("Market_and_Exchange_Names", "")),
                        market=rec.get("market", rec.get("Market_and_Exchange_Names", "")),
                        report_type=report_type,
                        date=rec.get("date", rec.get("As_of_Date_In_Form_YYMMDD", "")),
                        spec_long=int(rec.get("spec_long", rec.get("NonComm_Positions_Long_All", 0))),
                        spec_short=int(rec.get("spec_short", rec.get("NonComm_Positions_Short_All", 0))),
                        spec_net=int(rec.get("spec_net", 0)),
                        comm_long=int(rec.get("comm_long", rec.get("Comm_Positions_Long_All", 0))),
                        comm_short=int(rec.get("comm_short", rec.get("Comm_Positions_Short_All", 0))),
                        comm_net=int(rec.get("comm_net", 0)),
                        nonrept_long=int(rec.get("nonrept_long", rec.get("NonRept_Positions_Long_All", 0))),
                        nonrept_short=int(rec.get("nonrept_short", rec.get("NonRept_Positions_Short_All", 0))),
                        nonrept_net=int(rec.get("nonrept_net", 0)),
                        open_interest=int(rec.get("open_interest", rec.get("Open_Interest_All", 0))),
                        change_oi=int(rec.get("change_oi", rec.get("Change_in_Open_Interest_All", 0))),
                        change_spec_net=int(rec.get("change_spec_net", 0)),
                        category=rec.get("category", ""),
                    )
                    batch.append(pos)
                except (ValueError, KeyError, TypeError) as e:
                    skipped += 1
                    continue

            # Batch insert with conflict handling
            for pos in batch:
                try:
                    session.add(pos)
                    session.flush()
                    imported += 1
                except IntegrityError:
                    session.rollback()
                    skipped += 1

            if batch:
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()

        log.info("%s: %d imported so far", report_type, imported)

    log.info("COT total: %d imported, %d skipped", imported, skipped)
    return imported


def migrate_price_data(session, data_root: Path) -> int:
    """Import daily price snapshots from data/prices/."""
    prices_dir = data_root / "prices"
    if not prices_dir.exists():
        log.warning("Prices directory not found: %s", prices_dir)
        return 0

    imported = 0
    skipped = 0

    for price_file in sorted(prices_dir.glob("*.json")):
        try:
            data = json.loads(price_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        records = data if isinstance(data, list) else [data]

        for rec in records:
            try:
                price = PriceDaily(
                    instrument=rec.get("instrument", rec.get("symbol", "")),
                    date=rec.get("date", ""),
                    open=float(rec.get("open", 0)),
                    high=float(rec.get("high", 0)),
                    low=float(rec.get("low", 0)),
                    close=float(rec.get("close", 0)),
                    volume=int(rec.get("volume", 0)),
                    source=rec.get("source", "v1_migration"),
                )
                session.add(price)
                session.flush()
                imported += 1
            except (IntegrityError, ValueError, KeyError, TypeError):
                session.rollback()
                skipped += 1

    if imported:
        try:
            session.commit()
        except IntegrityError:
            session.rollback()

    log.info("Prices: %d imported, %d skipped", imported, skipped)
    return imported


def main():
    data_root = PROJECT_ROOT / "data"
    if not data_root.exists():
        log.error("Data directory not found: %s", data_root)
        log.error("This script expects v1 data in data/history/ and data/prices/")
        sys.exit(1)

    log.info("Initializing v2 database...")
    init_db()

    from sqlalchemy.orm import Session
    engine = get_engine()
    session = Session(bind=engine, expire_on_commit=False)

    try:
        log.info("--- Migrating COT data ---")
        cot_count = migrate_cot_data(session, data_root)

        log.info("--- Migrating price data ---")
        price_count = migrate_price_data(session, data_root)

        log.info("=== Migration complete ===")
        log.info("COT positions: %d", cot_count)
        log.info("Daily prices:  %d", price_count)

    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
