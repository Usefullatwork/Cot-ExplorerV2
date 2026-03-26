"""Migrate v1 Cot-Explorer historical data into v2 SQLite database.

Imports all 6 migratable data sources from the v1 flat-file layout:
  1. Instruments  — config/instruments.yaml  -> instruments table
  2. COT data     — data/cot/{report_type}/  -> cot_positions table
  3. Macro panels — data/prices/macro_latest.json -> macro_snapshots table
  4. Fundamentals — data/prices/fundamentals_latest.json -> fundamentals table
  5. Calendar     — data/prices/calendar_latest.json -> calendar_events table
  6. Audit trail  — logs the migration itself -> audit_log table

Idempotent: skips existing records via unique constraints.
Use --dry-run to preview what would be migrated without writing.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

from sqlalchemy.exc import IntegrityError

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.engine import get_engine, init_db
from src.db.models import (
    AuditLog,
    CalendarEvent,
    CotPosition,
    Fundamental,
    Instrument,
    MacroSnapshot,
)


# ---------------------------------------------------------------------------
# 1. Instruments (from YAML config)
# ---------------------------------------------------------------------------
def migrate_instruments(session, config_root: Path, dry_run: bool = False) -> int:
    """Import instruments from config/instruments.yaml."""
    yaml_path = config_root / "instruments.yaml"
    if not yaml_path.exists():
        log.warning("Instruments config not found: %s", yaml_path)
        return 0

    # Parse YAML without external dependency (simple key-value extraction)
    try:
        import yaml
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except ImportError:
        log.info("PyYAML not available, using fallback YAML parser")
        data = _parse_instruments_yaml_fallback(yaml_path)

    instruments_list = data.get("instruments", [])
    if not instruments_list:
        log.warning("No instruments found in %s", yaml_path)
        return 0

    imported = 0
    skipped = 0

    for inst in instruments_list:
        if dry_run:
            log.info("[DRY-RUN] Would import instrument: %s (%s)", inst.get("key"), inst.get("name"))
            imported += 1
            continue

        try:
            obj = Instrument(
                key=inst["key"],
                name=inst["name"],
                symbol=inst["symbol"],
                label=inst.get("label", ""),
                category=inst.get("category", ""),
                class_=inst.get("class", "C"),
                session=inst.get("session", ""),
                cot_market=inst.get("cot_market"),
                active=True,
            )
            session.merge(obj)  # merge = upsert by primary key
            session.flush()
            imported += 1
        except (IntegrityError, KeyError, TypeError) as e:
            session.rollback()
            log.warning("Skip instrument %s: %s", inst.get("key", "?"), e)
            skipped += 1

    if not dry_run and imported:
        try:
            session.commit()
        except IntegrityError:
            session.rollback()

    log.info("Instruments: %d imported, %d skipped%s", imported, skipped, " (dry-run)" if dry_run else "")
    return imported


def _parse_instruments_yaml_fallback(yaml_path: Path) -> dict:
    """Minimal YAML parser for the instruments config (no external deps).

    Handles the simple list-of-dicts format used in instruments.yaml.
    """
    text = yaml_path.read_text(encoding="utf-8")
    instruments = []
    current: dict | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # New section header
        if line == "instruments:":
            continue
        if line.startswith("macro_symbols:"):
            break  # Stop at macro_symbols section

        # New list item
        if line.startswith("- key:"):
            if current is not None:
                instruments.append(current)
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            current = {"key": value}
            continue

        # Key-value inside a list item
        if current is not None and ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.lower() == "null":
                val = None
            elif val.lower() in ("true", "false"):
                val = val.lower() == "true"
            if key and val is not None:
                current[key] = val
            elif key:
                current[key] = None

    if current is not None:
        instruments.append(current)

    return {"instruments": instruments}


# ---------------------------------------------------------------------------
# 2. COT Positions (from data/cot/{report_type}/*.json)
# ---------------------------------------------------------------------------
def migrate_cot_data(session, data_root: Path, dry_run: bool = False) -> int:
    """Import COT JSON files from data/cot/{report_type}/*.json.

    Handles both the v1 Norwegian nested format (spekulanter/kommersielle/
    institusjoner/meglere/smahandlere) and flat CFTC field names.
    """
    cot_dir = data_root / "cot"
    # Also check the old path for backward compat
    if not cot_dir.exists():
        cot_dir = data_root / "history"
    if not cot_dir.exists():
        log.warning("COT data directory not found in %s", data_root)
        return 0

    imported = 0
    skipped = 0

    for report_dir in sorted(cot_dir.iterdir()):
        if not report_dir.is_dir():
            continue
        report_type = report_dir.name

        for json_file in sorted(report_dir.glob("*.json")):
            try:
                raw = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                log.warning("SKIP %s: %s", json_file.name, e)
                continue

            records = raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else []

            for rec in records:
                try:
                    pos = _build_cot_position(rec, report_type)
                except (ValueError, KeyError, TypeError) as e:
                    skipped += 1
                    continue

                if dry_run:
                    log.info(
                        "[DRY-RUN] COT %s %s %s spec_net=%d",
                        pos.symbol, pos.report_type, pos.date, pos.spec_net,
                    )
                    imported += 1
                    continue

                try:
                    session.add(pos)
                    session.flush()
                    imported += 1
                except IntegrityError:
                    session.rollback()
                    skipped += 1

        if not dry_run:
            try:
                session.commit()
            except IntegrityError:
                session.rollback()

        log.info("%s: %d imported so far (%d skipped)", report_type, imported, skipped)

    log.info("COT total: %d imported, %d skipped%s", imported, skipped, " (dry-run)" if dry_run else "")
    return imported


def _build_cot_position(rec: dict, report_type: str) -> CotPosition:
    """Build a CotPosition ORM object from either v1 Norwegian or CFTC format."""
    # v1 Norwegian format uses nested dicts: spekulanter, kommersielle,
    # institusjoner, meglere, smahandlere
    spek = rec.get("spekulanter", {})
    komm = rec.get("kommersielle", {})
    inst = rec.get("institusjoner", {})
    megl = rec.get("meglere", {})
    smah = rec.get("smahandlere", {})

    # For TFF/disaggregated: spec = spekulanter, comm ~ meglere+institusjoner
    # For legacy: spec = spekulanter, comm = kommersielle
    if spek or komm or inst or megl or smah:
        spec_long = int(spek.get("long", 0))
        spec_short = int(spek.get("short", 0))
        spec_net = int(spek.get("net", 0))
        # Commercial = kommersielle (legacy) or meglere (TFF/disagg)
        if komm:
            comm_long = int(komm.get("long", 0))
            comm_short = int(komm.get("short", 0))
            comm_net = int(komm.get("net", 0))
        elif megl:
            comm_long = int(megl.get("long", 0))
            comm_short = int(megl.get("short", 0))
            comm_net = int(megl.get("net", 0))
        else:
            comm_long = comm_short = comm_net = 0
        nonrept_long = int(smah.get("long", 0))
        nonrept_short = int(smah.get("short", 0))
        nonrept_net = int(smah.get("net", 0))
    else:
        # Flat CFTC field names (fallback)
        spec_long = int(rec.get("spec_long", rec.get("NonComm_Positions_Long_All", 0)))
        spec_short = int(rec.get("spec_short", rec.get("NonComm_Positions_Short_All", 0)))
        spec_net = int(rec.get("spec_net", 0))
        comm_long = int(rec.get("comm_long", rec.get("Comm_Positions_Long_All", 0)))
        comm_short = int(rec.get("comm_short", rec.get("Comm_Positions_Short_All", 0)))
        comm_net = int(rec.get("comm_net", 0))
        nonrept_long = int(rec.get("nonrept_long", rec.get("NonRept_Positions_Long_All", 0)))
        nonrept_short = int(rec.get("nonrept_short", rec.get("NonRept_Positions_Short_All", 0)))
        nonrept_net = int(rec.get("nonrept_net", 0))

    symbol = rec.get("symbol", rec.get("Market_and_Exchange_Names", ""))
    market = rec.get("market", rec.get("Market_and_Exchange_Names", ""))
    date = rec.get("date", rec.get("As_of_Date_In_Form_YYMMDD", ""))
    rtype = rec.get("report", report_type)

    if not symbol or not date:
        raise ValueError(f"Missing symbol or date in COT record")

    return CotPosition(
        symbol=symbol,
        market=market,
        report_type=rtype,
        date=date,
        open_interest=int(rec.get("open_interest", rec.get("Open_Interest_All", 0))),
        change_oi=int(rec.get("change_oi", rec.get("Change_in_Open_Interest_All", 0))),
        spec_long=spec_long,
        spec_short=spec_short,
        spec_net=spec_net,
        comm_long=comm_long,
        comm_short=comm_short,
        comm_net=comm_net,
        nonrept_long=nonrept_long,
        nonrept_short=nonrept_short,
        nonrept_net=nonrept_net,
        change_spec_net=int(rec.get("change_spec_net", 0)),
        category=rec.get("kategori", rec.get("category", "")),
    )


# ---------------------------------------------------------------------------
# 3. Macro Snapshots (from data/prices/macro_latest.json)
# ---------------------------------------------------------------------------
def migrate_macro_data(session, data_root: Path, dry_run: bool = False) -> int:
    """Import macro snapshots from data/prices/macro_latest.json."""
    macro_path = data_root / "prices" / "macro_latest.json"
    if not macro_path.exists():
        log.warning("Macro data not found: %s", macro_path)
        return 0

    try:
        data = json.loads(macro_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning("SKIP macro data: %s", e)
        return 0

    vix_regime_obj = data.get("vix_regime", {})
    dollar_smile_obj = data.get("dollar_smile", {})
    prices = data.get("prices", {})

    vix_price = None
    vix_regime_label = None
    if isinstance(vix_regime_obj, dict):
        vix_price = vix_regime_obj.get("value")
        vix_regime_label = vix_regime_obj.get("regime")
    elif isinstance(vix_regime_obj, (int, float)):
        vix_price = float(vix_regime_obj)

    dollar_smile_pos = None
    usd_bias = None
    if isinstance(dollar_smile_obj, dict):
        dollar_smile_pos = dollar_smile_obj.get("position")
        usd_bias = dollar_smile_obj.get("usd_bias")

    # Parse the date string (format: "2026-03-26 00:37 UTC")
    date_str = data.get("date", "")
    try:
        generated_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M %Z").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        generated_at = datetime.now(timezone.utc)

    if dry_run:
        log.info(
            "[DRY-RUN] Would import macro snapshot: VIX=%.2f regime=%s dollar_smile=%s usd_bias=%s",
            vix_price or 0, vix_regime_label, dollar_smile_pos, usd_bias,
        )
        return 1

    try:
        snapshot = MacroSnapshot(
            generated_at=generated_at,
            vix_price=vix_price,
            vix_regime=vix_regime_label,
            dollar_smile=dollar_smile_pos,
            usd_bias=usd_bias,
            full_json=json.dumps(data, ensure_ascii=False),
        )
        session.add(snapshot)
        session.commit()
        log.info("Macro snapshot imported (VIX=%.2f, regime=%s)", vix_price or 0, vix_regime_label)
        return 1
    except IntegrityError:
        session.rollback()
        log.info("Macro snapshot already exists, skipped")
        return 0


# ---------------------------------------------------------------------------
# 4. Fundamentals (from data/prices/fundamentals_latest.json)
# ---------------------------------------------------------------------------
def migrate_fundamentals(session, data_root: Path, dry_run: bool = False) -> int:
    """Import fundamental indicators from data/prices/fundamentals_latest.json."""
    fund_path = data_root / "prices" / "fundamentals_latest.json"
    if not fund_path.exists():
        log.warning("Fundamentals data not found: %s", fund_path)
        return 0

    try:
        data = json.loads(fund_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning("SKIP fundamentals data: %s", e)
        return 0

    # Parse the updated timestamp
    updated_str = data.get("updated", "")
    try:
        updated_at = datetime.fromisoformat(updated_str)
    except (ValueError, TypeError):
        updated_at = datetime.now(timezone.utc)

    imported = 0
    skipped = 0

    # Import category-level scores
    for cat_key, cat_data in data.get("category_scores", {}).items():
        if not isinstance(cat_data, dict):
            continue

        if dry_run:
            log.info(
                "[DRY-RUN] Would import fundamental: %s score=%d bias=%s",
                cat_key, cat_data.get("score", 0), cat_data.get("bias", ""),
            )
            imported += 1
            continue

        try:
            obj = Fundamental(
                updated_at=updated_at,
                indicator_key=cat_key,
                label=cat_key.replace("_", " ").title(),
                current_value=float(cat_data.get("avg", 0)),
                previous_value=None,
                score=int(cat_data.get("score", 0)),
                trend=cat_data.get("bias"),
                date=updated_str[:10] if len(updated_str) >= 10 else None,
            )
            session.add(obj)
            session.flush()
            imported += 1
        except (IntegrityError, ValueError, TypeError) as e:
            session.rollback()
            log.warning("Skip fundamental %s: %s", cat_key, e)
            skipped += 1

    # Import instrument-level scores
    for inst_key, inst_data in data.get("instrument_scores", {}).items():
        if not isinstance(inst_data, dict):
            continue

        if dry_run:
            log.info(
                "[DRY-RUN] Would import instrument fundamental: %s score=%s",
                inst_key, inst_data.get("score", 0),
            )
            imported += 1
            continue

        try:
            obj = Fundamental(
                updated_at=updated_at,
                indicator_key=f"inst_{inst_key}",
                label=f"{inst_key} Fundamental Score",
                current_value=float(inst_data.get("score", 0)),
                previous_value=None,
                score=int(inst_data.get("score", 0)),
                trend=inst_data.get("bias"),
                date=updated_str[:10] if len(updated_str) >= 10 else None,
            )
            session.add(obj)
            session.flush()
            imported += 1
        except (IntegrityError, ValueError, TypeError) as e:
            session.rollback()
            log.warning("Skip instrument fundamental %s: %s", inst_key, e)
            skipped += 1

    if not dry_run and imported:
        try:
            session.commit()
        except IntegrityError:
            session.rollback()

    log.info("Fundamentals: %d imported, %d skipped%s", imported, skipped, " (dry-run)" if dry_run else "")
    return imported


# ---------------------------------------------------------------------------
# 5. Calendar Events (from data/prices/calendar_latest.json)
# ---------------------------------------------------------------------------
def migrate_calendar(session, data_root: Path, dry_run: bool = False) -> int:
    """Import calendar events from data/prices/calendar_latest.json."""
    cal_path = data_root / "prices" / "calendar_latest.json"
    if not cal_path.exists():
        log.warning("Calendar data not found: %s", cal_path)
        return 0

    try:
        data = json.loads(cal_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning("SKIP calendar data: %s", e)
        return 0

    events = data.get("events", [])
    if not isinstance(events, list):
        log.warning("Calendar events is not a list")
        return 0

    imported = 0
    skipped = 0

    for ev in events:
        if not isinstance(ev, dict):
            skipped += 1
            continue

        # Parse the date string (ISO format with timezone)
        date_str = ev.get("date", "")
        try:
            event_date = datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            skipped += 1
            continue

        title = ev.get("title", "")
        country = ev.get("country", "")
        impact = ev.get("impact", "")

        if not title or not country:
            skipped += 1
            continue

        if dry_run:
            log.info("[DRY-RUN] Would import event: %s %s (%s) %s", date_str[:10], title, country, impact)
            imported += 1
            continue

        try:
            obj = CalendarEvent(
                date=event_date,
                title=title,
                country=country,
                impact=impact,
                forecast=ev.get("forecast", ""),
                previous=ev.get("previous", ""),
                actual=ev.get("actual", ""),
                hours_away=float(ev["hours_away"]) if ev.get("hours_away") is not None else None,
                affected_instruments=json.dumps(ev.get("berorte", []), ensure_ascii=False),
            )
            session.add(obj)
            session.flush()
            imported += 1
        except (IntegrityError, ValueError, TypeError) as e:
            session.rollback()
            log.warning("Skip calendar event '%s': %s", title, e)
            skipped += 1

    if not dry_run and imported:
        try:
            session.commit()
        except IntegrityError:
            session.rollback()

    log.info("Calendar: %d imported, %d skipped%s", imported, skipped, " (dry-run)" if dry_run else "")
    return imported


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_migration(session) -> bool:
    """Verify imported data integrity: record counts and key fields non-null.

    Returns True if all checks pass, False otherwise.
    """
    log.info("=== Validating migration integrity ===")
    passed = True

    checks = [
        ("instruments", Instrument, ["key", "name", "symbol"]),
        ("cot_positions", CotPosition, ["symbol", "market", "date", "report_type"]),
        ("macro_snapshots", MacroSnapshot, ["generated_at"]),
        ("fundamentals", Fundamental, ["indicator_key", "label"]),
        ("calendar_events", CalendarEvent, ["date", "title", "country"]),
    ]

    for table_name, model, required_fields in checks:
        count = session.query(model).count()
        log.info("  %-20s %6d records", table_name, count)

        if count == 0:
            # Not an error — data source may simply be absent
            log.info("  %-20s (no data — source files may be missing)", table_name)
            continue

        # Check that required fields are non-null on all records
        for field_name in required_fields:
            col = getattr(model, field_name, None)
            if col is None:
                continue
            null_count = session.query(model).filter(col.is_(None)).count()
            if null_count > 0:
                log.warning(
                    "  WARN: %s.%s has %d NULL values (expected 0)",
                    table_name, field_name, null_count,
                )
                passed = False

        # Spot-check: verify first record can be loaded
        first = session.query(model).first()
        if first is None:
            log.warning("  WARN: %s query returned None despite count=%d", table_name, count)
            passed = False

    if passed:
        log.info("=== Validation PASSED ===")
    else:
        log.warning("=== Validation completed with WARNINGS ===")

    return passed


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate v1 Cot-Explorer data into v2 SQLite database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be migrated without writing to the database.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip post-migration validation checks.",
    )
    args = parser.parse_args()

    data_root = PROJECT_ROOT / "data"
    config_root = PROJECT_ROOT / "config"

    if not data_root.exists():
        log.error("Data directory not found: %s", data_root)
        log.error("This script expects v1 data in data/cot/ and data/prices/")
        sys.exit(1)

    if args.dry_run:
        log.info("=== DRY-RUN MODE — no database writes ===")
    else:
        log.info("Initializing v2 database...")
        init_db()

    from sqlalchemy.orm import Session as SASession
    engine = get_engine()
    session = SASession(bind=engine, expire_on_commit=False) if not args.dry_run else None

    totals: dict[str, int] = {}

    try:
        # 1. Instruments
        log.info("--- [1/5] Migrating instruments ---")
        totals["instruments"] = migrate_instruments(session, config_root, dry_run=args.dry_run)

        # 2. COT positions
        log.info("--- [2/5] Migrating COT data ---")
        totals["cot_positions"] = migrate_cot_data(session, data_root, dry_run=args.dry_run)

        # 3. Macro snapshots
        log.info("--- [3/5] Migrating macro data ---")
        totals["macro_snapshots"] = migrate_macro_data(session, data_root, dry_run=args.dry_run)

        # 4. Fundamentals
        log.info("--- [4/5] Migrating fundamentals ---")
        totals["fundamentals"] = migrate_fundamentals(session, data_root, dry_run=args.dry_run)

        # 5. Calendar events
        log.info("--- [5/5] Migrating calendar events ---")
        totals["calendar_events"] = migrate_calendar(session, data_root, dry_run=args.dry_run)

        # Log the migration in audit_log
        if not args.dry_run and session is not None:
            audit_entry = AuditLog(
                timestamp=datetime.now(timezone.utc),
                event_type="v1_migration",
                details=json.dumps(totals, ensure_ascii=False),
            )
            session.add(audit_entry)
            session.commit()

        # Summary
        log.info("=== Migration complete ===")
        for table, count in totals.items():
            log.info("  %-20s %6d records", table, count)
        grand_total = sum(totals.values())
        log.info("  %-20s %6d total", "GRAND TOTAL", grand_total)

        # Validation
        if not args.dry_run and not args.skip_validation and session is not None:
            validate_migration(session)

    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    main()
